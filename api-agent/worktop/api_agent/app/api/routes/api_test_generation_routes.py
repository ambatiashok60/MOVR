"""Public API test generation routes (ScriptGen / test_agent parity).

The caller submits a test case row — hierarchy id, testcase id, steps — and
never decides where the repository lives: the repo path is resolved
server-side from datasource configuration (payload value is a standalone
fallback only), the tenant comes from the authenticated request context, and
the testcase name is loaded best-effort from the platform DAO.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request

from worktop.api_agent.app.api.deps import get_db
from worktop.api_agent.app.api.security import (
    require_permission,
    resolve_tenant,
    resolve_user_name,
)
from worktop.api_agent.app.schemas.api_test_generation_request import (
    GenerateApiTestCodeRequest,
    GenerateApiTestsRequest,
)
from worktop.api_agent.app.schemas.queued_task import QueuedTask
from worktop.api_agent.app.services.repository_resolution_service import (
    load_testcase_name,
    resolve_repository_path,
)
from worktop.api_agent.app.task_managers.api_test_generation_task_manager import (
    enqueue_api_tests_task,
    enqueue_api_test_code_generation_task,
)
from worktop.api_agent.app.utils.logging_utils import log_step

router = APIRouter(
    prefix="/api/api-test-generation",
    tags=["api-test-generation"],
)


@router.post("/generate-api-test-code", response_model=QueuedTask)
@require_permission("AUTOMATION_EXECUTION", "execute")
async def generate_api_test_code(
    request: Request,
    payload: GenerateApiTestCodeRequest = Body(...),
    db: Any = Depends(get_db),
) -> QueuedTask:
    tenant_id = resolve_tenant(request=request, payload_tenant_id=payload.tenant_id)
    resolved = payload.model_copy(
        update={
            "tenant_id": tenant_id,
            "repo_path": resolve_repository_path(db, payload.repo_path),
        }
    )
    task_id = enqueue_api_test_code_generation_task(resolved, db=db)
    log_step(
        "api_test_code_generation_queued",
        {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "hierarchy_id": payload.user_story_hierarchy_id,
            "api_scenario_id": payload.api_scenario_id,
            "requested_by": resolve_user_name(request),
        },
    )
    return QueuedTask(task_id=task_id)


@router.post("/generateApiTests", response_model=QueuedTask)
@require_permission("AUTOMATION_EXECUTION", "execute")
async def generate_api_tests(
    request: Request,
    payload: GenerateApiTestsRequest = Body(...),
    db: Any = Depends(get_db),
) -> QueuedTask:
    tenant_id = resolve_tenant(request=request, payload_tenant_id=payload.tenant_id)
    testcase_name = payload.testcase_name or load_testcase_name(
        db=db,
        user_story_hierarchy_id=payload.user_story_hierarchy_id,
        testcase_id=payload.testcase_id,
    )
    resolved = payload.model_copy(
        update={
            "tenant_id": tenant_id,
            "repo_path": resolve_repository_path(db, payload.repo_path),
            "testcase_name": testcase_name or payload.testcase_name,
        }
    )
    task_id = enqueue_api_tests_task(resolved, db=db)
    log_step(
        "api_test_generation_queued",
        {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "hierarchy_id": payload.user_story_hierarchy_id,
            "testcase_id": payload.testcase_id,
            "testcase_steps": len(payload.testcase_steps),
            "requested_by": resolve_user_name(request),
        },
    )
    return QueuedTask(task_id=task_id)
