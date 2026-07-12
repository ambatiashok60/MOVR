from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from worktop.test_agent.app.adapters.script_gen_adapter import ScriptGenAdapter
from worktop.test_agent.app.api.deps import get_db
from worktop.test_agent.app.api.security import (
    require_permission,
    resolve_tenant,
    resolve_user_name,
)
from worktop.test_agent.app.runtime import scriptgen_runtime
from worktop.test_agent.app.schemas.generation_status import JOB_QUEUED
from worktop.test_agent.app.schemas.playwright_generation_api import (
    GenerationAcceptedResponse,
    PlaywrightGenerationRequest,
)
from worktop.test_agent.app.services.generation_job_store import generation_job_store
from worktop.core_services.app.utility.custom_logger.logging import logger


router = APIRouter(prefix="/api/playwright", tags=["Playwright Generation"])


def _resolve_repository_path(db: Any) -> str:
    """Resolve the server-side repository path from datasource configuration."""
    try:
        from worktop.core_services.app.dao.data_source_dao import DataSourceDAO
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository datasource is not configured in this deployment",
        ) from exc
    properties = DataSourceDAO.get_latest_github_properties(db) or {}
    repo_path = (properties.get("local_repo_path") or "").strip()
    if not repo_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository path is not configured in datasource properties",
        )
    return repo_path


def _load_testcase_name(
    *, db: Any, user_story_hierarchy_id: int, testcase_id: str
) -> str:
    """Best-effort testcase-name lookup; a failure must not block generation."""
    try:
        from worktop.core_services.app.dao.test_cases_generation_dao import (
            TestcasesGenerationDAO,
        )
    except Exception:
        return ""
    try:
        testcase = TestcasesGenerationDAO.get_testcase_by_id(
            db, int(user_story_hierarchy_id), testcase_id
        )
        return getattr(testcase, "testcase_name", "") or ""
    except Exception:
        logger.exception(
            "Failed to load testcase name | hierarchy_id=%s testcase_id=%s",
            user_story_hierarchy_id,
            testcase_id,
        )
        return ""


@router.post(
    "/generate",
    response_model=GenerationAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@require_permission("AUTOMATION_EXECUTION", "execute")
async def generate_playwright_test(
    request: Request,
    payload: PlaywrightGenerationRequest = Body(...),
    db: Any = Depends(get_db),
) -> GenerationAcceptedResponse:
    job_id = str(uuid.uuid4())
    tenant_id = resolve_tenant(request=request, payload_tenant_id=payload.tenant_id)

    testcase_name = _load_testcase_name(
        db=db,
        user_story_hierarchy_id=payload.user_story_hierarchy_id,
        testcase_id=payload.testcase_id,
    )
    requested_by = resolve_user_name(request)
    repo_path = _resolve_repository_path(db)

    flow_steps = ScriptGenAdapter.extract_flow_steps(
        db, payload.user_story_hierarchy_id
    )
    combined_steps, flow_steps_count = ScriptGenAdapter.prepend_flow_steps(
        flow_steps, list(payload.testcase_steps)
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
        tenant_id=tenant_id,
        user_story_id=payload.user_story_id,
        row_id=payload.row_id,
        testcase_name=testcase_name,
        requested_by=requested_by,
        automation_steps_count=len(payload.testcase_steps),
        flow_steps_count=flow_steps_count,
    )

    try:
        scriptgen_runtime.enqueue_agent_generation_task(
            job_id=job_id,
            user_story_hierarchy_id=payload.user_story_hierarchy_id,
            testcase_id=payload.testcase_id,
            tenant_id=tenant_id,
            generation_request=generation_request.model_dump(mode="json"),
            user_story_id=payload.user_story_id,
            row_id=payload.row_id,
        )
    except scriptgen_runtime.RuntimeUnavailableError as exc:
        generation_job_store.fail(job_id, "generation runtime unavailable")
        logger.error(
            "Generation runtime unavailable | job_id=%s tenant_id=%s",
            job_id,
            tenant_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Generation runtime is not available in this deployment",
        ) from exc

    logger.info(
        "Playwright generation queued | job_id=%s tenant_id=%s hierarchy_id=%s "
        "testcase_id=%s flow_steps=%s testcase_steps=%s",
        job_id,
        tenant_id,
        payload.user_story_hierarchy_id,
        payload.testcase_id,
        flow_steps_count,
        len(payload.testcase_steps),
    )

    return GenerationAcceptedResponse(
        job_id=job_id,
        status=JOB_QUEUED,
        testcase_id=payload.testcase_id,
        user_story_hierarchy_id=payload.user_story_hierarchy_id,
        automation_steps_count=len(payload.testcase_steps),
        flow_steps_count=flow_steps_count,
    )
