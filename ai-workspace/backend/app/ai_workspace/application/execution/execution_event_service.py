from datetime import datetime, timezone

from app.ai_workspace.domain.execution_context import ExecutionStage, ExecutionStageStatus
from app.ai_workspace.domain.execution_event import ExecutionEvent, ExecutionEventType
from app.ai_workspace.infrastructure.sse_event_publisher import SseEventPublisher


class ExecutionEventService:
    """Publishes timeline events and keeps an ExecutionContext's `stages` list in sync with
    them — the only writer of stages, so the SSE stream and the polled execution status
    (GET /api/executions/{id}) never disagree about what happened."""

    def __init__(self, publisher: SseEventPublisher):
        self._publisher = publisher

    async def start_stage(self, execution, stage_id: str, label: str) -> None:
        execution.stages.append(ExecutionStage(id=stage_id, label=label, status=ExecutionStageStatus.ACTIVE))
        await self._publish(execution.execution_id, ExecutionEventType.STAGE_STARTED, label, None)

    async def complete_stage(self, execution, stage_id: str, detail: str | None = None) -> None:
        for stage in execution.stages:
            if stage.id == stage_id:
                stage.status = ExecutionStageStatus.DONE
                stage.detail = detail
        await self._publish(execution.execution_id, ExecutionEventType.STAGE_COMPLETED, stage_id, detail)

    async def fail_stage(self, execution, stage_id: str, detail: str) -> None:
        for stage in execution.stages:
            if stage.id == stage_id:
                stage.status = ExecutionStageStatus.FAILED
                stage.detail = detail
        await self._publish(execution.execution_id, ExecutionEventType.STAGE_FAILED, stage_id, detail)

    async def tool_call(self, execution, tool_name: str, detail: str | None = None) -> None:
        await self._publish(execution.execution_id, ExecutionEventType.TOOL_CALL, tool_name, detail)

    async def completed(self, execution) -> None:
        await self._publish(execution.execution_id, ExecutionEventType.COMPLETED, "Run completed", None)

    async def _publish(self, execution_id: str, event_type: ExecutionEventType, label: str, detail: str | None) -> None:
        event = ExecutionEvent(
            execution_id=execution_id,
            event_type=event_type,
            label=label,
            detail=detail,
            created_at=datetime.now(timezone.utc),
        )
        await self._publisher.publish(event)
