from __future__ import annotations

from fastapi import APIRouter

from worktop.api_agent.app.schemas.generation_job import GenerationJob
from worktop.api_agent.app.task_managers.api_test_generation_task_manager import (
    abort_api_generation_task,
    abort_api_test_task,
    get_api_generation_task_status,
    get_api_generation_task_status_by_key,
    make_api_test_key,
)

router = APIRouter(
    prefix="/api/api-test-generation",
    tags=["api-test-generation-jobs"],
)


@router.get("/jobs/{task_id}", response_model=GenerationJob)
def get_generation_job(task_id: str) -> GenerationJob:
    return get_api_generation_task_status(task_id)


@router.post("/abort/{task_id}", response_model=GenerationJob)
def abort_generation_job(task_id: str) -> GenerationJob:
    return abort_api_generation_task(task_id)


@router.get("/jobs/by-key/{tenant_id}/{user_story_hierarchy_id}/{testcase_id}", response_model=GenerationJob)
def get_generation_job_by_key(
    tenant_id: int,
    user_story_hierarchy_id: int,
    testcase_id: str,
    row_id: str | None = None,
) -> GenerationJob:
    key = make_api_test_key(tenant_id, user_story_hierarchy_id, testcase_id, row_id)
    return get_api_generation_task_status_by_key(key)


@router.post("/abort/by-key/{tenant_id}/{user_story_hierarchy_id}/{testcase_id}", response_model=GenerationJob)
def abort_generation_job_by_key(
    tenant_id: int,
    user_story_hierarchy_id: int,
    testcase_id: str,
    row_id: str | None = None,
) -> GenerationJob:
    key = make_api_test_key(tenant_id, user_story_hierarchy_id, testcase_id, row_id)
    return abort_api_test_task(key)
