import asyncio
import json

from app.ai_workspace.domain.execution_event import ExecutionEvent


class SseEventPublisher:
    """In-process pub/sub for execution events, keyed by execution id. sse_routes.py subscribes
    (async generator, one per open connection); execution_event_service.py publishes.

    Single-process only, same caveat as the in-memory stores — a multi-instance deployment
    needs this backed by something shared (Redis pub/sub is the natural fit) instead of an
    in-memory asyncio.Queue per execution.
    """

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}

    def subscribe(self, execution_id: str) -> asyncio.Queue:
        queue = self._queues.setdefault(execution_id, asyncio.Queue())
        return queue

    async def publish(self, event: ExecutionEvent) -> None:
        queue = self._queues.setdefault(event.execution_id, asyncio.Queue())
        await queue.put(_serialize(event))

    def close(self, execution_id: str) -> None:
        self._queues.pop(execution_id, None)


def _serialize(event: ExecutionEvent) -> str:
    return json.dumps(
        {
            "execution_id": event.execution_id,
            "event_type": event.event_type.value,
            "label": event.label,
            "detail": event.detail,
            "created_at": event.created_at.isoformat(),
        }
    )
