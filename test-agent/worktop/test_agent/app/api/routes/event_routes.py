from __future__ import annotations

import uuid
from queue import Queue as ThreadQueue

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from worktop.test_agent.app.api.security import validate_job_tenant
from worktop.test_agent.app.runtime import scriptgen_runtime
from worktop.test_agent.app.services.generation_job_store import generation_job_store
from worktop.core_services.app.utility.custom_logger.logging import logger


router = APIRouter(prefix="/api/playwright/events", tags=["generation-events"])


@router.get("/{job_id}")
async def stream_generation_events(
    job_id: str, request: Request
) -> StreamingResponse:
    job = generation_job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job '{job_id}' was not found",
        )
    validate_job_tenant(request, job)

    try:
        key = scriptgen_runtime.make_key(
            job["user_story_hierarchy_id"],
            job["testcase_id"],
            job["tenant_id"],
        )
        # Task manager publishes on a standard thread Queue (not asyncio.Queue).
        queue: ThreadQueue[str] = ThreadQueue(maxsize=100)
        # subscribe replays buffered events so a late subscriber still sees the
        # early queued/in-progress states.
        scriptgen_runtime.subscribe_scriptgen_status(key, queue)
    except scriptgen_runtime.RuntimeUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Generation event stream is not available in this deployment",
        ) from exc

    connection_id = str(uuid.uuid4())[:8]
    last_event_id = request.headers.get("Last-Event-ID")
    logger.info(
        "Generation SSE connected | job_id=%s key=%s connection_id=%s",
        job_id,
        key,
        connection_id,
    )

    return StreamingResponse(
        scriptgen_runtime.generation_status_event_generator(
            request=request,
            queues=[(key, queue)],
            connection_id=connection_id,
            last_event_id=last_event_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # disable proxy buffering so SSE flushes promptly
            "X-Accel-Buffering": "no",
        },
    )
