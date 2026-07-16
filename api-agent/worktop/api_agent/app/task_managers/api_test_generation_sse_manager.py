from __future__ import annotations

import asyncio
import json
from collections import defaultdict, deque
from collections.abc import AsyncIterator

from worktop.api_agent.app.config import settings
from worktop.api_agent.app.schemas.event import GenerationEvent


class ApiTestGenerationSseManager:
    def __init__(self) -> None:
        self._buffers: dict[str, deque[GenerationEvent]] = defaultdict(
            lambda: deque(maxlen=settings.max_event_buffer)
        )

    def publish(
        self,
        task_id: str,
        event_type: str,
        stage: str,
        message: str,
        payload: dict | None = None,
    ) -> GenerationEvent:
        event = GenerationEvent(
            task_id=task_id,
            event_type=event_type,
            stage=stage,
            message=message,
            payload=payload or {},
        )
        self._buffers[task_id].append(event)
        return event

    def get_events(self, task_id: str) -> list[GenerationEvent]:
        return list(self._buffers.get(task_id, []))

    async def stream(self, task_id: str) -> AsyncIterator[str]:
        cursor = 0
        while True:
            events = self.get_events(task_id)
            while cursor < len(events):
                event = events[cursor]
                cursor += 1
                yield self._format(event)
                if event.event_type in {"completed", "failed", "aborted"}:
                    return
            yield f"event: heartbeat\ndata: {json.dumps({'task_id': task_id})}\n\n"
            await asyncio.sleep(2)

    def _format(self, event: GenerationEvent) -> str:
        data = event.model_dump_json()
        return f"event: {event.event_type}\ndata: {data}\n\n"


sse_manager = ApiTestGenerationSseManager()
