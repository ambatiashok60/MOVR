from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/playwright/events", tags=["generation-events"])


@router.get("/{job_id}")
def stream_generation_events(job_id: str) -> StreamingResponse:
    async def events():
        yield f"event: heartbeat\ndata: {job_id}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
