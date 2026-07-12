from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from worktop.test_agent.app.api.security import validate_job_tenant
from worktop.test_agent.app.runtime import scriptgen_runtime
from worktop.test_agent.app.schemas.generation_job import GenerationJob
from worktop.test_agent.app.schemas.generation_status import (
    JOB_ABORT_REQUESTED,
    TERMINAL_JOB_STATUSES,
)
from worktop.test_agent.app.schemas.playwright_generation_api import (
    GenerationAbortResponse,
)
from worktop.test_agent.app.services.generation_job_store import generation_job_store
from worktop.core_services.app.utility.custom_logger.logging import logger


router = APIRouter(prefix="/api/playwright/jobs", tags=["generation-jobs"])


def _serialize_result(result: Any) -> dict[str, Any] | None:
    if result is None:
        return None
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if isinstance(result, dict):
        return result
    return {"value": str(result)}


@router.get("/{job_id}", response_model=GenerationJob)
def get_generation_job(job_id: str, request: Request) -> GenerationJob:
    job = generation_job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job '{job_id}' was not found",
        )
    validate_job_tenant(request, job)
    return GenerationJob(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
        testcase_id=job["testcase_id"],
        user_story_hierarchy_id=job["user_story_hierarchy_id"],
        created_at=job.get("created_at"),
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        result=_serialize_result(job.get("result")),
        error=job.get("error"),
        automation_steps_count=job.get("automation_steps_count", 0),
        flow_steps_count=job.get("flow_steps_count", 0),
    )


@router.post("/{job_id}/abort", response_model=GenerationAbortResponse)
def abort_generation_job(job_id: str, request: Request) -> GenerationAbortResponse:
    job = generation_job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job '{job_id}' was not found",
        )
    validate_job_tenant(request, job)

    if job["status"] in TERMINAL_JOB_STATUSES:
        return GenerationAbortResponse(
            job_id=job_id,
            status=job["status"],
            message="Job is already in a terminal state",
        )

    try:
        result = scriptgen_runtime.abort_task(
            user_story_hierarchy_id=job["user_story_hierarchy_id"],
            testcase_id=job["testcase_id"],
            tenant_id=job["tenant_id"],
            user_story_id=job.get("user_story_id"),
            row_id=job.get("row_id"),
        )
    except scriptgen_runtime.RuntimeUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Generation runtime is not available in this deployment",
        ) from exc

    generation_job_store.mark_abort_requested(job_id)
    result = result if isinstance(result, dict) else {}
    logger.info(
        "Generation abort requested | job_id=%s tenant_id=%s status=%s",
        job_id,
        job["tenant_id"],
        result.get("status", JOB_ABORT_REQUESTED),
    )
    return GenerationAbortResponse(
        job_id=job_id,
        status=result.get("status", JOB_ABORT_REQUESTED),
        message=result.get("message"),
    )
