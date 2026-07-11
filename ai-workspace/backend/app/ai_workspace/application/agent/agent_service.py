import json
import logging
import hashlib
import uuid
from typing import Any

from app.ai_workspace.application.context.context_builder_service import ContextBuilderService
from app.ai_workspace.application.prompts.prompt_builder_service import PromptBuilderService
from app.ai_workspace.application.prompts.prompt_renderer import PromptRenderer
from app.ai_workspace.application.review.diff_service import DiffService
from app.ai_workspace.application.review.review_service import ReviewService
from app.ai_workspace.application.sessions.session_service import SessionService
from app.ai_workspace.domain.chat_message import ChatRole
from app.ai_workspace.domain.execution_context import ExecutionContext, ExecutionStage, ExecutionStageStatus
from app.ai_workspace.domain.execution_plan import ExecutionPlan, ExecutionPlanStep
from app.ai_workspace.domain.file_change import FileChange, FileChangeStatus
from app.ai_workspace.domain.agent_turn import AgentTurn, ToolObservation
from app.ai_workspace.application.agent.patch_validation_service import PatchValidationService
from app.ai_workspace.application.tools.base_tool import ToolExecutionContext
from app.ai_workspace.application.tools.tool_execution_service import ToolExecutionService
from app.ai_workspace.application.execution.execution_event_service import ExecutionEventService
from app.common.data_governance import DataGovernanceService
from app.ai_workspace.application.review.engineering_review_service import EngineeringReviewService
from app.repository.application.isolated_workspace_service import IsolatedWorkspaceService
from app.llm.application.llm_application_service import LLMApplicationService
from app.repository.application.file_read_service import FileReadService
from app.utils.logging_utils import build_log_context, log_metric, log_step

_STAGE_CONTEXT = "build_context"
_STAGE_LLM = "llm_completion"
_STAGE_DIFF = "build_diffs"
_STAGE_DISCOVERY = "iterative_discovery"
_STAGE_VALIDATION = "validate_patch"
logger = logging.getLogger(__name__)
MAX_AGENT_TURNS = 8
MAX_IDENTICAL_TOOL_CALLS = 2
_ITERATIVE_SYSTEM_PROMPT = """You are an evidence-driven coding agent. Return ONLY JSON matching:
{"status":"needs_evidence|ready_to_patch|completed|blocked","reasoning_summary":str,
"root_cause":str|null,"evidence":[str],"tool_calls":[{"id":str,"tool_name":"read_file|search_repository|list_files","arguments":{},"reason":str}],
"plan":{"steps":[{"description":str,"affected_files":[str],"confidence":float}]},
"file_changes":[{"path":str,"status":"added|modified|deleted","new_content":str,"rationale":str,"evidence":[str]}],"final_summary":str|null}.
Explore until the root cause is proven. Prefer nearby repository conventions and the smallest safe change. Complete file contents only. Never request write/apply tools."""


class AgentPlanParseError(ValueError):
    pass


class AgentService:
    """Implements ExecutionOrchestrator's ExecutionStrategy for Agent mode.

    See prompt_renderer.py's _AGENT_SYSTEM_PROMPT docstring for why this is a single
    structured-JSON-response design rather than a true iterative tool-calling loop for V1.
    File changes are staged via ReviewService (write-to-disk only happens later, through
    apply_patch_tool.py, when the user applies kept changes) — this method never writes to
    the workspace itself.
    """

    def __init__(
        self,
        context_builder: ContextBuilderService,
        prompt_builder: PromptBuilderService,
        prompt_renderer: PromptRenderer,
        llm_service: LLMApplicationService,
        session_service: SessionService,
        file_read_service: FileReadService,
        diff_service: DiffService,
        review_service: ReviewService,
        plan_store: Any,
        tool_execution_service: ToolExecutionService,
        event_service: ExecutionEventService,
        patch_validator: PatchValidationService | None = None,
        engineering_review_service: EngineeringReviewService | None = None,
        isolated_workspace_service: IsolatedWorkspaceService | None = None,
        repository_memory_service=None,
    ):
        self._context_builder = context_builder
        self._prompt_builder = prompt_builder
        self._prompt_renderer = prompt_renderer
        self._llm_service = llm_service
        self._session_service = session_service
        self._file_read_service = file_read_service
        self._diff_service = diff_service
        self._review_service = review_service
        self._plan_store = plan_store
        self._tools = tool_execution_service
        self._events = event_service
        self._patch_validator = patch_validator or PatchValidationService()
        self._engineering_review = engineering_review_service or EngineeringReviewService()
        self._isolated_workspace = isolated_workspace_service
        self._memory = repository_memory_service

    async def run(self, execution: ExecutionContext, runtime) -> None:
        log_step(
            "ai_workspace_agent_started",
            build_log_context(
                session_id=execution.session_id,
                execution_id=execution.execution_id,
                workspace_path=runtime.workspace_path,
                stage="agent",
            ),
        )
        self._session_service.record_message(execution.session_id, ChatRole.USER, execution.prompt)

        await self._events.start_stage(execution, _STAGE_CONTEXT, "Building context")
        context = self._context_builder.build(runtime)
        await self._events.complete_stage(execution, _STAGE_CONTEXT, f"{len(context.files)} selected files; {context.redaction_count} redactions")

        await self._events.start_stage(execution, _STAGE_DISCOVERY, "Discovering repository evidence")
        structured_prompt = self._prompt_builder.build(runtime.mode, execution.prompt, context)
        system_prompt, user_prompt = self._prompt_renderer.render(structured_prompt)
        turn, observations = await self._run_agent_loop(execution, runtime, system_prompt, user_prompt)
        await self._events.complete_stage(execution, _STAGE_DISCOVERY, f"{len(observations)} tool observations; root cause: {turn.root_cause or 'not stated'}")

        await self._events.start_stage(execution, _STAGE_VALIDATION, "Validating proposed changes")
        validation = self._patch_validator.validate(turn.file_changes)
        if not validation.passed:
            turn = await self._repair_patch(execution, turn, validation.findings, system_prompt, user_prompt)
            validation = self._patch_validator.validate(turn.file_changes)
        if not validation.passed:
            await self._events.fail_stage(execution, _STAGE_VALIDATION, "; ".join(validation.findings[:5]))
            raise ValueError("Proposed patch failed deterministic validation")
        if self._isolated_workspace:
            execution.isolated_workspace_path = self._isolated_workspace.stage(
                execution.execution_id, runtime.workspace_path, turn.file_changes
            )
            logger.info("Patch staged in isolated workspace | execution_id=%s | path=%s", execution.execution_id, execution.isolated_workspace_path)
        await self._events.complete_stage(execution, _STAGE_VALIDATION, "; ".join(validation.findings) or "Structural validation passed")
        execution.engineering_review = self._engineering_review.build(turn, validation, len(observations))
        if self._memory and turn.root_cause:
            self._memory.remember(runtime.workspace_path, turn.root_cause, turn.evidence, [c.path for c in turn.file_changes])
        if execution.engineering_review["remaining_risks"]:
            execution.needs_review = True
            execution.review_reasons.extend(execution.engineering_review["remaining_risks"])
        logger.info(
            "Engineering review completed | execution_id=%s | score=%s | risk=%s | confidence=%s",
            execution.execution_id,
            execution.engineering_review["quality_score"],
            execution.engineering_review["risk_level"],
            execution.engineering_review["confidence"],
        )

        payload = {"plan": turn.plan, "file_changes": [item.model_dump() for item in turn.file_changes]}

        budget = self._llm_service.budget_report(execution.execution_id)
        if budget:
            execution.budget_usage = {
                "llm_calls": budget.usage.llm_calls,
                "prompt_characters": budget.usage.prompt_characters,
                "completion_characters": budget.usage.completion_characters,
                "elapsed_seconds": budget.usage.elapsed_seconds,
            }
            if budget.review_required:
                execution.needs_review = True
                execution.review_reasons.extend(budget.findings)

        plan = _build_plan(execution.execution_id, payload.get("plan", {}))
        self._plan_store.save(plan)

        await self._events.start_stage(execution, _STAGE_DIFF, "Building review diffs")
        file_changes = self._build_file_changes(execution, runtime, payload.get("file_changes", []))
        await self._events.complete_stage(execution, _STAGE_DIFF, f"{len(file_changes)} file changes staged")

        self._review_service.save_proposed_changes(execution.execution_id, file_changes)
        log_metric("ai_workspace_agent_plan_step_count", len(plan.steps))
        log_metric("ai_workspace_agent_file_change_count", len(file_changes))
        log_step(
            "ai_workspace_agent_completed",
            build_log_context(session_id=execution.session_id, execution_id=execution.execution_id, stage="agent"),
        )

        self._session_service.record_message(
            execution.session_id,
            ChatRole.ASSISTANT,
            f"Proposed {len(file_changes)} file change(s) across {len(plan.steps)} step(s).",
            execution_id=execution.execution_id,
        )

    async def _run_agent_loop(self, execution, runtime, system_prompt: str, user_prompt: str) -> tuple[AgentTurn, list[ToolObservation]]:
        observations: list[ToolObservation] = []
        call_counts: dict[str, int] = {}
        governance = DataGovernanceService()
        for turn_index in range(1, MAX_AGENT_TURNS + 1):
            logger.info("Agent discovery turn %s/%s | execution_id=%s | observations=%s", turn_index, MAX_AGENT_TURNS, execution.execution_id, len(observations))
            observation_text = json.dumps([item.model_dump() for item in observations], default=str)[-30000:]
            completion = self._llm_service.complete(
                execution.execution_id,
                _ITERATIVE_SYSTEM_PROMPT,
                f"{user_prompt}\n\n## Tool observations\n{observation_text}\n\nTurn {turn_index} of {MAX_AGENT_TURNS}.",
            )
            turn = _parse_agent_turn(completion.text)
            logger.info("Agent decision | execution_id=%s | status=%s | tools=%s | evidence=%s", execution.execution_id, turn.status, len(turn.tool_calls), len(turn.evidence))
            if turn.status in {"ready_to_patch", "completed"}:
                if not turn.root_cause or not turn.evidence:
                    observations.append(ToolObservation(tool_call_id="policy", tool_name="evidence_gate", success=False, summary="Patch rejected: root cause and repository evidence are required."))
                    continue
                return turn, observations
            if turn.status == "blocked":
                raise RuntimeError(turn.final_summary or turn.reasoning_summary)
            if not turn.tool_calls:
                observations.append(ToolObservation(tool_call_id="policy", tool_name="turn_policy", success=False, summary="No tool calls supplied while more evidence was requested."))
                continue
            for call in turn.tool_calls:
                signature = f"{call.tool_name}:{json.dumps(call.arguments, sort_keys=True)}"
                call_counts[signature] = call_counts.get(signature, 0) + 1
                if call_counts[signature] > MAX_IDENTICAL_TOOL_CALLS:
                    observations.append(ToolObservation(tool_call_id=call.id, tool_name=call.tool_name, success=False, summary="Repeated identical tool call blocked."))
                    continue
                await self._events.tool_call(execution, call.tool_name, call.reason)
                try:
                    result = self._tools.execute(call.tool_name, ToolExecutionContext(runtime.workspace_path, execution.tenant_id), call.arguments)
                    if call.tool_name == "read_file" and "content" in result:
                        released = governance.release(str(result.get("path", "")), str(result["content"]))
                        result["content"] = released if released is not None else "[BLOCKED BY DATA POLICY]"
                    observations.append(ToolObservation(tool_call_id=call.id, tool_name=call.tool_name, success=True, summary=call.reason, result=_bounded_result(result)))
                    logger.info("Tool completed | execution_id=%s | tool=%s | call_id=%s", execution.execution_id, call.tool_name, call.id)
                except Exception as exc:
                    observations.append(ToolObservation(tool_call_id=call.id, tool_name=call.tool_name, success=False, summary=call.reason, error=str(exc)))
                    logger.warning("Tool failed | execution_id=%s | tool=%s | error=%s", execution.execution_id, call.tool_name, exc)
        raise RuntimeError(f"Agent discovery exhausted {MAX_AGENT_TURNS} turns without an evidence-backed patch")

    async def _repair_patch(self, execution, turn: AgentTurn, findings: list[str], system_prompt: str, user_prompt: str) -> AgentTurn:
        logger.warning("Patch repair started | execution_id=%s | findings=%s", execution.execution_id, findings[:5])
        completion = self._llm_service.complete(execution.execution_id, _ITERATIVE_SYSTEM_PROMPT, f"{user_prompt}\n\nRepair this proposed turn:\n{turn.model_dump_json()}\n\nValidation findings:\n" + "\n".join(findings) + "\nReturn a corrected ready_to_patch turn.")
        return _parse_agent_turn(completion.text)

    def _build_file_changes(self, execution: ExecutionContext, runtime, raw_changes: list[dict]) -> list[FileChange]:
        changes: list[FileChange] = []
        for raw in raw_changes:
            path = raw["path"]
            status = FileChangeStatus(raw.get("status", "modified"))
            new_content = raw["new_content"]

            old_content = ""
            if status != FileChangeStatus.ADDED:
                try:
                    old_content = self._file_read_service.read(runtime.workspace_path, path).content
                except (FileNotFoundError, OSError):
                    old_content = ""

            hunks = self._diff_service.build_hunks(old_content, new_content)
            additions, deletions = self._diff_service.count_changes(hunks)

            changes.append(
                FileChange(
                    id=str(uuid.uuid4()),
                    run_id=execution.execution_id,
                    file_path=path,
                    status=status,
                    additions=additions,
                    deletions=deletions,
                    new_content=new_content,
                    diff_hunks=hunks,
                    original_digest=hashlib.sha256(old_content.encode()).hexdigest(),
                    original_existed=status != FileChangeStatus.ADDED and bool(old_content or self._file_exists(runtime.workspace_path, path)),
                )
            )
        return changes

    def _file_exists(self, workspace_path: str, path: str) -> bool:
        try:
            self._file_read_service.read(workspace_path, path)
            return True
        except (FileNotFoundError, OSError):
            return False


def _parse_json_response(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = next((index for index, char in enumerate(text) if char in "{["), None)
        if start is None:
            raise AgentPlanParseError("Model response did not contain a JSON object")
        stack: list[str] = []
        pairs = {"{": "}", "[": "]"}
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped: escaped = False
                elif char == "\\": escaped = True
                elif char == '"': in_string = False
                continue
            if char == '"': in_string = True
            elif char in pairs: stack.append(pairs[char])
            elif stack and char == stack[-1]:
                stack.pop()
                if not stack:
                    try:
                        return json.loads(text[start:index + 1])
                    except json.JSONDecodeError as exc:
                        raise AgentPlanParseError(f"Extracted model JSON was invalid: {exc}") from exc
        raise AgentPlanParseError("Model response contained incomplete JSON")


def _parse_agent_turn(text: str) -> AgentTurn:
    payload = _parse_json_response(text)
    # Backward compatibility for the original one-shot response contract.
    if "status" not in payload and "plan" in payload:
        payload = {
            "status": "ready_to_patch",
            "reasoning_summary": "Legacy one-shot plan",
            "root_cause": "Root cause inferred from selected repository context.",
            "evidence": ["Selected repository context supplied by the user."],
            **payload,
        }
    return AgentTurn.model_validate(payload)


def _bounded_result(result: dict, max_chars: int = 12_000) -> dict:
    encoded = json.dumps(result, default=str)
    if len(encoded) <= max_chars:
        return result
    return {"truncated": True, "content": encoded[:max_chars]}


def _build_plan(execution_id: str, raw_plan: dict) -> ExecutionPlan:
    steps = [
        ExecutionPlanStep(
            order=index,
            description=step.get("description", ""),
            affected_files=step.get("affected_files", []),
            confidence=step.get("confidence"),
        )
        for index, step in enumerate(raw_plan.get("steps", []), start=1)
    ]
    return ExecutionPlan(execution_id=execution_id, steps=steps)
from typing import Any
