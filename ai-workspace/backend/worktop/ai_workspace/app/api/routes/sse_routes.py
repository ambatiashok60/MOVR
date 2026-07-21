import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from worktop.ai_workspace.app.ai_workspace.domain.execution_event import ExecutionEventType
from worktop.ai_workspace.app.ai_workspace.infrastructure.sse_event_publisher import SseEventPublisher
from worktop.ai_workspace.app.dependencies.container import container

router = APIRouter(prefix="/ai-workspace/agent/executions", tags=["SSE"])

_HEARTBEAT_SECONDS = 15


def get_sse_publisher() -> SseEventPublisher:
    return container.sse_publisher


@router.get("/{execution_id}/events")
async def stream_execution_events(execution_id: str, publisher: SseEventPublisher = Depends(get_sse_publisher)):
    queue = publisher.subscribe(execution_id)

    async def event_generator():
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
                    yield f"data: {payload}\n\n"
                    # Close server-side once the run is done, rather than only relying on the
                    # client to disconnect — the connection would otherwise stay open (sending
                    # heartbeats) until the browser tab closes it.
                    if json.loads(payload).get("event_type") == ExecutionEventType.COMPLETED.value:
                        break
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            publisher.close(execution_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
