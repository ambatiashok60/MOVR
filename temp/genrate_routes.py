from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from worktop.test_agent.app.adapters.script_gen_adapter import ScriptGenAdapter
from worktop.test_agent.app.api.deps import get_db
from worktop.test_agent.app.runtime import scriptgen_runtime
from worktop.test_agent.app.schemas.generation_status import JOB_QUEUED
from worktop.test_agent.app.schemas.playwright_generation_api import (
    GenerationAcceptedResponse,
    PlaywrightGenerationRequest,
)
from worktop.test_agent.app.services.generation_job_store import (
    generation_job_store,
)
from worktop.test_agent.utils.logging import get_logger

@router.post(
    "/generateTestScripts",
    response_model=GenerationAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@JWTokenService.permission_required_async(
    features.get(
        "AUTOMATION_EXECUTION",
        "AUTOMATION_EXECUTION",
    ),
    "execute",
)
async def generate_playwright_scripts(
    request: Request,
    payload: PlaywrightGenerationRequest = Body(...),
    db: Any = Depends(get_db),
) -> GenerationAcceptedResponse:
    """
    Validate and enqueue Playwright generation.

    This endpoint does not run generation synchronously. The existing Script
    Generator worker owns execution and SSE lifecycle delivery.
    """
    job_id = str(uuid.uuid4())

    tenant_id = getattr(
        request.state,
        "tenant_id",
        None,
    )

    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated tenant ID is unavailable.",
        )

    requested_by = (
        getattr(request.state, "user_name", None)
        or getattr(request.state, "username", None)
        or "system"
    )

    testcase_name = _load_testcase_name(
        db=db,
        user_story_hierarchy_id=payload.user_story_hierarchy_id,
        testcase_id=payload.testcase_id,
    )

    repo_path = _resolve_repository_path(db)

    flow_steps = ScriptGenAdapter.extract_flow_steps(
        db,
        payload.user_story_hierarchy_id,
    )

    combined_steps, flow_steps_count = (
        ScriptGenAdapter.prepend_flow_steps(
            flow_steps,
            list(payload.testcase_steps),
        )
    )

    generation_request = ScriptGenAdapter.to_generation_request(
        job_id=job_id,
        repo_path=repo_path,
        tenant_id=tenant_id,
        testcase_id=payload.testcase_id,
        automation_steps=combined_steps,
        branch=None,
        run_validation=payload.run_validation,
        testcase_name=testcase_name,
    )

    generation_job_store.create(
        job_id=job_id,
        user_story_hierarchy_id=payload.user_story_hierarchy_id,
        testcase_id=payload.testcase_id,
        tenant_id=int(tenant_id),
        user_story_id=payload.user_story_id,
        row_id=payload.row_id,
        testcase_name=testcase_name,
        requested_by=requested_by,
        automation_steps_count=len(payload.testcase_steps),
        flow_steps_count=flow_steps_count,
        metadata={
            "repo_path": repo_path,
            "combined_steps_count": len(combined_steps),
        },
    )

    try:
        scriptgen_runtime.enqueue_agent_generation_task(
            job_id=job_id,
            user_story_hierarchy_id=payload.user_story_hierarchy_id,
            testcase_id=payload.testcase_id,
            tenant_id=int(tenant_id),
            generation_request=generation_request.model_dump(
                mode="json"
            ),
            user_story_id=payload.user_story_id,
            row_id=payload.row_id,
            requested_by=requested_by,
        )

    except scriptgen_runtime.RuntimeUnavailableError as exc:
        generation_job_store.fail(job_id, exc)

        logger.exception(
            "Generation runtime unavailable | job_id=%s",
            job_id,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Generation runtime is unavailable in this deployment."
            ),
        ) from exc

    except Exception as exc:
        generation_job_store.fail(job_id, exc)

        logger.exception(
            "Failed to enqueue Playwright generation | job_id=%s",
            job_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue Playwright generation.",
        ) from exc

    logger.info(
        "Playwright generation queued | "
        "job_id=%s tenant_id=%s hierarchy_id=%s testcase_id=%s "
        "flow_steps=%s testcase_steps=%s total_steps=%s",
        job_id,
        tenant_id,
        payload.user_story_hierarchy_id,
        payload.testcase_id,
        flow_steps_count,
        len(payload.testcase_steps),
        len(combined_steps),
    )

    return GenerationAcceptedResponse(
        job_id=job_id,
        status=JOB_QUEUED,
        testcase_id=payload.testcase_id,
        user_story_hierarchy_id=(
            payload.user_story_hierarchy_id
        ),
        automation_steps_count=len(payload.testcase_steps),
        flow_steps_count=flow_steps_count,
    )