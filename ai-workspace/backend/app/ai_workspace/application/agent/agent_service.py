import json
import uuid

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
from app.llm.application.llm_application_service import LLMApplicationService
from app.repository.application.file_read_service import FileReadService
from app.utils.logging_utils import build_log_context, log_metric, log_step

_STAGE_CONTEXT = "build_context"
_STAGE_LLM = "llm_completion"
_STAGE_DIFF = "build_diffs"


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

        execution.stages.append(ExecutionStage(id=_STAGE_CONTEXT, label="Building context", status=ExecutionStageStatus.ACTIVE))
        context = self._context_builder.build(runtime)
        execution.stages[-1].status = ExecutionStageStatus.DONE

        execution.stages.append(ExecutionStage(id=_STAGE_LLM, label="Planning changes", status=ExecutionStageStatus.ACTIVE))
        structured_prompt = self._prompt_builder.build(runtime.mode, execution.prompt, context)
        system_prompt, user_prompt = self._prompt_renderer.render(structured_prompt)
        completion = self._llm_service.complete(execution.execution_id, system_prompt, user_prompt)

        try:
            payload = _parse_json_response(completion.text)
        except AgentPlanParseError as exc:
            execution.stages[-1].status = ExecutionStageStatus.FAILED
            execution.stages[-1].detail = str(exc)
            raise
        execution.stages[-1].status = ExecutionStageStatus.DONE

        plan = _build_plan(execution.execution_id, payload.get("plan", {}))
        self._plan_store.save(plan)

        execution.stages.append(ExecutionStage(id=_STAGE_DIFF, label="Building diffs", status=ExecutionStageStatus.ACTIVE))
        file_changes = self._build_file_changes(execution, runtime, payload.get("file_changes", []))
        execution.stages[-1].status = ExecutionStageStatus.DONE

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
                )
            )
        return changes


def _parse_json_response(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AgentPlanParseError(f"Model response was not valid JSON: {exc}") from exc


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
