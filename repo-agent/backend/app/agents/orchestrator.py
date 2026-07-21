"""The run lifecycle: plan -> (decide -> act -> observe -> update)* -> validate
-> compose response -> terminal state.

Guarantees every run reaches a terminal state and emits a terminal event, so a
run never goes silent (dead-hang prevention starts here on the backend).
"""

from __future__ import annotations

from app.agents.decision_engine import DecisionEngine
from app.agents.observation_manager import ObservationManager
from app.agents.planner import Planner
from app.agents.response_composer import ResponseComposer
from app.changes.change_manager import ChangeManager
from app.changes.snapshot_manager import SnapshotManager
from app.context.context_manager import ContextManager
from app.llm.client_factory import build_llm_client
from app.logging.agent_logger import agent_logger
from app.logging.context import conversation_id_ctx, run_id_ctx, workspace_id_ctx
from app.models.agent import AgentRunError, AgentRunRequest, AgentRunView
from app.models.enums import AgentMode, AgentState, RunStatus, StreamEventType
from app.persistence.repositories import (
    ConversationRepository,
    MessageRepository,
    RunArtifactRepository,
    RunRepository,
)
from app.streaming.event_bus import EventBus
from app.tools.executor import ToolExecutor
from app.context.repository_index import RepositoryIndex
from app.tools.registry import ToolPermissionError
from app.validation.validation_manager import ValidationManager
from app.workspace.workspace_manager import WorkspaceError, WorkspaceManager

_READ_TOOLS = {"list_directory", "get_repository_summary", "search_code", "read_file",
               "read_file_range", "find_symbol", "find_references"}


class AgentOrchestrator:
    def __init__(
        self,
        *,
        event_bus: EventBus,
        runs: RunRepository,
        conversations: ConversationRepository,
        messages: MessageRepository,
        artifacts: RunArtifactRepository,
    ) -> None:
        self._bus = event_bus
        self._runs = runs
        self._conversations = conversations
        self._messages = messages
        self._artifacts = artifacts
        self._executor = ToolExecutor()
        self._observations = ObservationManager()
        self._context = ContextManager(conversations, messages)
        self._snapshots = SnapshotManager()
        self._changes = ChangeManager(artifacts, self._snapshots)
        self._validation = ValidationManager()
        self._workspaces = WorkspaceManager()

    async def run(self, request: AgentRunRequest, run: AgentRunView) -> None:
        run_id = run.run_id
        run_id_ctx.set(run_id)
        conversation_id_ctx.set(run.conversation_id)
        workspace_id_ctx.set(request.workspace_path)

        counts = {"tools": 0, "reads": 0, "mods": 0}
        try:
            await self._bus.publish(run_id, StreamEventType.RUN_STARTED, {
                "mode": request.mode.value, "message": request.message,
                "workspace": request.workspace_path,
            })
            agent_logger.run_started({
                "run_id": run_id, "conversation": run.conversation_id, "mode": request.mode.value,
                "workspace": request.workspace_path, "request": request.message[:60],
            })

            workspace = self._workspaces.open_workspace(request.workspace_path)
            repo_index = RepositoryIndex(workspace)

            # --- context compaction (§12) --------------------------------
            ctx = self._context.prepare_conversation(run.conversation_id)
            if ctx.compacted:
                await self._bus.publish(run_id, StreamEventType.CONVERSATION_COMPACTED, {
                    "conversation_id": run.conversation_id,
                    "compacted_through_turn": ctx.compacted_through_turn,
                    "recent_turns_retained": ctx.recent_turns_retained,
                })
                agent_logger.compaction_completed({
                    "conversation": run.conversation_id,
                    "through_turn": ctx.compacted_through_turn,
                    "retained": ctx.recent_turns_retained,
                })

            # --- per-run LLM (with reauth callbacks) ---------------------
            llm = build_llm_client(
                provider=("bedrock" if request.aws_profile or request.model_id else None),
                profile=request.aws_profile, region=request.aws_region, model_id=request.model_id,
                on_reauth_required=lambda p: self._on_reauth_required(run_id, p),
                on_reauthenticated=lambda p: self._on_reauthenticated(run_id, p),
            )
            planner = Planner(llm)
            engine = DecisionEngine(llm)
            composer = ResponseComposer(self._bus, self._artifacts, llm)

            # --- planning -------------------------------------------------
            self._runs.set_status(run_id, RunStatus.PLANNING, AgentState.PLANNING.value)
            plan = await planner.create_plan(
                user_request=request.message, mode=request.mode, repo_summary=repo_index.summary
            )
            self._artifacts.save_plan(run_id, plan)
            self._runs.update_counters(run_id, plan_revision=plan.revision)
            await self._bus.publish(run_id, StreamEventType.PLAN_CREATED, {"plan": plan.model_dump()})
            agent_logger.plan_created({
                "run_id": run_id, "revision": plan.revision,
                "steps": [f"{s.step_id} {s.title}" for s in plan.steps],
            })

            # --- Plan-Act-Observe-Decide loop ----------------------------
            self._runs.set_status(run_id, RunStatus.RUNNING, AgentState.SELECTING_ACTION.value)
            observations: list[str] = []
            changed_files: list[str] = []
            validation_summaries: list[str] = []

            for _ in range(max(1, request.max_agent_iterations)):
                decision = await engine.decide(
                    user_request=request.message, mode=request.mode, plan=plan,
                    observations=observations, repo_summary=repo_index.summary,
                )

                if decision.action == "tool_call" and decision.tool_call:
                    await self._execute_tool(run_id, workspace, request.mode, decision, counts,
                                             observations, changed_files)
                    plan = planner.advance(plan, observations[-1] if observations else "")
                    self._artifacts.save_plan(run_id, plan)
                    self._runs.update_counters(run_id, plan_revision=plan.revision)
                    await self._bus.publish(run_id, StreamEventType.PLAN_UPDATED, {"plan": plan.model_dump()})

                elif decision.action == "validate":
                    results = await self._run_validation(run_id, workspace, changed_files)
                    validation_summaries += results
                    # Record an observation so the loop advances past this step
                    # (otherwise the decision engine can re-request validation).
                    observations.append("[validation] " + "; ".join(results))

                elif decision.action == "fail":
                    await self._fail(run_id, AgentRunError(
                        code="AGENT_DECIDED_FAIL", message=decision.reason or "Agent failed",
                        recoverable=True, retry_action="resume_run"))
                    return

                else:  # respond
                    break

            # --- final validation for agent runs that never asked --------
            if request.mode == AgentMode.AGENT and request.enable_validation and not validation_summaries:
                validation_summaries += await self._run_validation(run_id, workspace, changed_files)

            # --- compose the answer --------------------------------------
            self._runs.set_status(run_id, RunStatus.COMPLETING, AgentState.RESPONDING.value)
            batch_count = await composer.stream_final_response(
                run_id=run_id, user_request=request.message, mode=request.mode,
                observations=observations, changed_files=changed_files, validation=validation_summaries,
            )

            self._persist_assistant_turn(run)

            self._runs.set_status(run_id, RunStatus.COMPLETED, AgentState.COMPLETED.value)
            await self._bus.publish(run_id, StreamEventType.RUN_COMPLETED, {
                "status": RunStatus.COMPLETED.value, "total_batches": batch_count,
                "files_read": counts["reads"], "tool_calls": counts["tools"],
                "files_modified": counts["mods"],
            })
            agent_logger.run_completed({
                "run_id": run_id, "files_read": counts["reads"], "tool_calls": counts["tools"],
                "files_modified": counts["mods"], "response_parts": batch_count,
            })

        except (WorkspaceError, ToolPermissionError) as exc:
            await self._fail(run_id, AgentRunError(
                code="WORKSPACE_ERROR" if isinstance(exc, WorkspaceError) else "TOOL_PERMISSION_DENIED",
                message=str(exc), recoverable=False, retry_action="none"))
        except Exception as exc:  # noqa: BLE001 - any failure must still terminate the run
            await self._fail(run_id, AgentRunError(
                code="RUN_FAILED", message=str(exc), recoverable=True, retry_action="start_new_run"))

    # --- helpers -----------------------------------------------------------
    async def _execute_tool(self, run_id, workspace, mode, decision, counts,
                            observations, changed_files) -> None:
        call = decision.tool_call
        await self._bus.publish(run_id, StreamEventType.TOOL_STARTED, {
            "tool_call_id": call.tool_call_id, "tool_name": call.tool_name,
            "plan_step_id": call.plan_step_id, "arguments": call.arguments,
        })
        agent_logger.tool_started({"run_id": run_id, "tool": call.tool_name, "call_id": call.tool_call_id})

        if mode == AgentMode.AGENT:
            self._snapshots.snapshot(run_id, workspace)

        result = await self._executor.execute(workspace=workspace, mode=mode, tool_call=call)
        counts["tools"] += 1
        if call.tool_name in _READ_TOOLS and result.success:
            counts["reads"] += 1

        observations.append(self._observations.normalize(result))
        await self._bus.publish(run_id, StreamEventType.OBSERVATION_CREATED, {
            "tool_call_id": call.tool_call_id, "summary": result.summary,
        })

        change = self._changes.record_from_tool(run_id, result, call.plan_step_id)
        if change:
            counts["mods"] += 1
            changed_files.append(change.path)

        event = StreamEventType.TOOL_COMPLETED if result.success else StreamEventType.TOOL_FAILED
        await self._bus.publish(run_id, event, {
            "tool_call_id": call.tool_call_id, "tool_name": call.tool_name,
            "success": result.success, "summary": result.summary, "duration_ms": result.duration_ms,
        })
        self._runs.update_counters(run_id, tool_call_count=counts["tools"],
                                   files_read_count=counts["reads"], files_modified_count=counts["mods"])
        log = agent_logger.tool_completed if result.success else agent_logger.tool_failed
        log({"run_id": run_id, "tool": call.tool_name, "call_id": call.tool_call_id,
             "duration_ms": result.duration_ms, "result": result.summary})

    async def _run_validation(self, run_id, workspace, changed_files) -> list[str]:
        self._runs.set_status(run_id, RunStatus.VALIDATING, AgentState.VALIDATING.value)
        await self._bus.publish(run_id, StreamEventType.VALIDATION_STARTED, {"changed_files": changed_files})
        results = self._validation.validate(workspace, changed_files)
        for result in results:
            self._artifacts.add_validation(run_id, result)
        await self._bus.publish(run_id, StreamEventType.VALIDATION_COMPLETED, {
            "results": [r.model_dump() for r in results],
        })
        agent_logger.validation_completed({
            "run_id": run_id, "results": [f"{r.name}: {r.status}" for r in results]})
        self._runs.set_status(run_id, RunStatus.RUNNING, AgentState.SELECTING_ACTION.value)
        return [f"{r.name}: {r.status}" for r in results]

    def _persist_assistant_turn(self, run: AgentRunView) -> None:
        batches = self._artifacts.list_response_batches(run.run_id)
        content = "\n\n".join(b.markdown for b in batches).strip() or "(response)"
        self._messages.add(run.conversation_id, "assistant", content, run_id=run.run_id)
        turns = self._messages.get_turns(run.conversation_id)
        self._conversations.touch(run.conversation_id, turn_count=len(turns))

    async def _fail(self, run_id: str, error: AgentRunError) -> None:
        self._runs.set_error(run_id, error)
        self._runs.set_status(run_id, RunStatus.FAILED, AgentState.FAILED.value)
        await self._bus.publish(run_id, StreamEventType.RUN_FAILED, {
            "error": error.model_dump(), "status": RunStatus.FAILED.value,
        })
        agent_logger.run_failed({"run_id": run_id, "code": error.code, "message": error.message})

    async def _on_reauth_required(self, run_id: str, profile: str) -> None:
        self._runs.set_status(run_id, RunStatus.WAITING_FOR_AUTH)
        await self._bus.publish(run_id, StreamEventType.AWS_REAUTHENTICATION_REQUIRED, {"profile": profile})

    async def _on_reauthenticated(self, run_id: str, profile: str) -> None:
        self._runs.set_status(run_id, RunStatus.RUNNING)
        await self._bus.publish(run_id, StreamEventType.AWS_REAUTHENTICATED, {"profile": profile})
