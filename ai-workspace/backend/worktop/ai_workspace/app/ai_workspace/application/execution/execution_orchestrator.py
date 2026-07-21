import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from worktop.ai_workspace.app.ai_workspace.application.execution.execution_event_service import ExecutionEventService
from worktop.ai_workspace.app.ai_workspace.application.workspace_runtime_service import WorkspaceRuntimeService
from worktop.ai_workspace.app.ai_workspace.domain.execution_context import ExecutionContext, ExecutionStatus
from worktop.ai_workspace.app.ai_workspace.domain.workspace_mode import WorkspaceMode
from worktop.ai_workspace.app.utils.logging_utils import build_log_context, log_exception, log_metric, log_performance, log_step


class ExecutionStrategy(Protocol):
    """Ask/Agent-specific behavior. ChatService and AgentService both implement this — the
    orchestrator only knows it can await strategy.run(execution, runtime); everything about
    what tools are available, whether planning happens, and whether a review step is needed
    lives inside the strategy, not here (this is the Strategy pattern discussed for the
    execution pipeline: shared lifecycle in the orchestrator, mode-specific behavior in the
    strategy)."""

    async def run(self, execution: ExecutionContext, runtime) -> None: ...


class ExecutionOrchestrator:
    """Owns the execution lifecycle shared by both modes: create the ExecutionContext, resolve
    the workspace runtime, transition status, catch and record failures, emit the final
    'completed' event. Session/context/prompt building and LLM calls all happen inside
    whichever strategy is selected for the run's mode."""

    def __init__(
        self,
        strategies: dict[WorkspaceMode, ExecutionStrategy],
        runtime_service: WorkspaceRuntimeService,
        event_service: ExecutionEventService,
        execution_store: Any,
    ):
        self._strategies = strategies
        self._runtime_service = runtime_service
        self._event_service = event_service
        self._execution_store = execution_store

    @log_performance("ai_workspace_execution.run")
    async def run(self, session_id: str, tenant_id: str, mode: WorkspaceMode, prompt: str) -> ExecutionContext:
        runtime = self._runtime_service.get(session_id)
        if runtime is None:
            raise ValueError(f"No active workspace runtime for session {session_id}")

        execution = ExecutionContext(
            execution_id=str(uuid.uuid4()),
            session_id=session_id,
            tenant_id=tenant_id,
            mode=mode,
            prompt=prompt,
            correlation_id=str(uuid.uuid4()),
            started_at=datetime.now(timezone.utc),
            status=ExecutionStatus.RUNNING,
        )
        context = build_log_context(
            session_id=session_id,
            tenant_id=tenant_id,
            execution_id=execution.execution_id,
            mode=mode.value,
            workspace_path=runtime.workspace_path,
            stage="execution",
        )
        log_step("ai_workspace_execution_started", context)

        strategy = self._strategies[mode]
        try:
            await strategy.run(execution, runtime)
            execution.status = ExecutionStatus.COMPLETED
            log_metric("ai_workspace_execution_stage_count", len(execution.stages))
            log_step("ai_workspace_execution_completed", context)
        except Exception as exc:  # noqa: BLE001 — deliberately broad: any strategy failure must
            # still produce a well-formed ExecutionContext for the frontend, not an unhandled 500.
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(exc)
            log_exception(exc, context=context)
        finally:
            execution.completed_at = datetime.now(timezone.utc)

        await self._event_service.completed(execution)
        self._execution_store.save(execution)
        return execution
