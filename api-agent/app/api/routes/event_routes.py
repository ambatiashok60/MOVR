from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.task_managers.api_test_generation_sse_manager import sse_manager
from app.task_managers.api_test_generation_task_manager import (
    get_api_generation_task_status_by_key,
    make_api_test_key,
)

router = APIRouter(
    prefix="/api/api-test-generation",
    tags=["api-test-generation-events"],
)


@router.get("/events/{task_id}")
def stream_generation_events(task_id: str) -> StreamingResponse:
    return StreamingResponse(
        sse_manager.stream(task_id),
        media_type="text/event-stream",
    )


@router.get("/events/by-key/{tenant_id}/{user_story_hierarchy_id}/{testcase_id}")
def stream_generation_events_by_key(
    tenant_id: int,
    user_story_hierarchy_id: int,
    testcase_id: str,
    row_id: str | None = None,
) -> StreamingResponse:
    key = make_api_test_key(tenant_id, user_story_hierarchy_id, testcase_id, row_id)
    job = get_api_generation_task_status_by_key(key)
    return StreamingResponse(
        sse_manager.stream(job.task_id),
        media_type="text/event-stream",
    )
