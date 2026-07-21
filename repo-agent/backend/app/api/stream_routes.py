"""SSE endpoint with replay support (§22)."""

from __future__ import annotations

from fastapi import APIRouter

from app.streaming.event_bus import get_event_bus
from app.streaming.sse_manager import sse_response

router = APIRouter(prefix="/api/agent-runs", tags=["stream"])


@router.get("/{run_id}/events")
async def stream_events(run_id: str, after_sequence: int = 0):
    # Reconnecting clients pass ?after_sequence=N; the server replays persisted
    # events after N, then resumes the live stream — no duplicate rendering.
    return sse_response(get_event_bus(), run_id, after_sequence)
