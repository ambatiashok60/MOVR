"""Builds the SSE StreamingResponse: replay -> live -> heartbeat -> terminal close."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from starlette.responses import StreamingResponse

from app.models.enums import StreamEventType
from app.models.stream import StreamEvent
from app.streaming.event_bus import EventBus

_TERMINAL = {StreamEventType.RUN_COMPLETED, StreamEventType.RUN_FAILED, StreamEventType.RUN_CANCELLED}

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable proxy buffering (nginx)
}


def _heartbeat_frame(run_id: str, sequence: int) -> str:
    body = json.dumps({"run_id": run_id, "sequence": sequence, "status": "active"})
    return f"event: {StreamEventType.HEARTBEAT.value}\ndata: {body}\n\n"


async def _event_stream(bus: EventBus, run_id: str, after_sequence: int) -> AsyncIterator[str]:
    # 1) Replay everything the client missed (idempotent via sequence on the client).
    for row in bus.replay_after(run_id, after_sequence):
        event = StreamEvent(
            run_id=run_id, sequence=row["sequence"],
            event_type=StreamEventType(row["event_type"]), payload=row["payload"],
        )
        yield event.to_sse()
        if event.event_type in _TERMINAL:
            return  # run already finished; nothing live to wait for

    # 2) Subscribe to live events, interleaving heartbeats on idle.
    queue = bus.subscribe(run_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=bus.heartbeat_interval)
            except asyncio.TimeoutError:
                yield _heartbeat_frame(run_id, bus.current_sequence(run_id))
                if bus.is_terminal(run_id):
                    return
                continue
            yield event.to_sse()
            if event.event_type in _TERMINAL:
                return
    finally:
        bus.unsubscribe(run_id, queue)


def sse_response(bus: EventBus, run_id: str, after_sequence: int = 0) -> StreamingResponse:
    return StreamingResponse(
        _event_stream(bus, run_id, after_sequence),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
