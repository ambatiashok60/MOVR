from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from worktop.admin_services.app.services.jw_token_service import (
    JWTokenService,
)
from worktop.config.db import get_db
from worktop.core.services.app.dao.data_source_dao import DataSourceDAO
from worktop.core.services.app.dao.test_cases_generation_dao import (
    TestcasesGenerationDAO,
)
from worktop.core.services.app.dao.user_story_hierarchy_dao import (
    UserStoryHierarchyDAO,
)
from worktop.core.services.app.utility.custom_logger.logging import logger
from worktop.script_generator.app.task_managers.script_generation_task_manager import (
    enqueue_scriptgen_task,
)
from worktop.test_agent.app.adapters.script_gen_adapter import (
    ScriptGenAdapter,
)
from worktop.test_agent.app.schemas.generation_status import JOB_QUEUED
from worktop.test_agent.app.schemas.playwright_generation_api import (
    GenerationAcceptedResponse,
    PlaywrightGenerationRequest,
)
from worktop.test_agent.app.services.generation_job_store import (
    generation_job_store,
)
from worktop.utility.api_envelope import EnvelopeRouter


router = EnvelopeRouter(
    tags=["Playwright Test Generation"],
)


@router.post(
    "/generateTestScripts",
    response_model=GenerationAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_playwright_scripts(
    request: Request,
    payload: PlaywrightGenerationRequest = Body(...),
    db: Session = Depends(get_db),
) -> GenerationAcceptedResponse:
    """
    Prepare an agentic generation request and enqueue it into the
    existing ScriptGen task manager.

    The existing ScriptGen queue, worker, abort handling and SSE
    infrastructure are reused. The worker_type field tells the worker
    to use the new GenerationOrchestrator execution function.
    """

    job_id = str(uuid.uuid4())

    testcase_id = payload.testcase_id
    user_story_hierarchy_id = payload.user_story_hierarchy_id
    user_story_id = payload.user_story_id
    row_id = payload.row_id

    # Replace this once tenant extraction is available from JWT/request.
    tenant_id = 1

    # -----------------------------------------------------------------
    # Resolve requesting user
    # -----------------------------------------------------------------
    user_info = JWTokenService.get_user_name_from_request(request)
    requested_by = (
        user_info.get("user_name", "system")
        if user_info
        else "system"
    )

    # -----------------------------------------------------------------
    # Load testcase name
    # -----------------------------------------------------------------
    testcase_name = ""

    try:
        testcase_row = TestcasesGenerationDAO.get_testcase_by_id(
            db,
            int(user_story_hierarchy_id),
            testcase_id,
        )

        if testcase_row:
            testcase_name = (
                getattr(
                    testcase_row,
                    "testcase_name",
                    "",
                )
                or ""
            ).strip()

    except Exception as exc:
        logger.warning(
            "[AGENTIC SCRIPTGEN] Could not load testcase name | "
            "ush_id=%s testcase_id=%s error=%s",
            user_story_hierarchy_id,
            testcase_id,
            str(exc),
        )

    if not testcase_name:
        testcase_name = str(testcase_id)

    # -----------------------------------------------------------------
    # Load shared flow steps
    # -----------------------------------------------------------------
    flow_steps: list[str] = []

    try:
        flow_steps = ScriptGenAdapter.extract_flow_steps(
            db,
            user_story_hierarchy_id,
        )
    except Exception as exc:
        # Flow steps are best effort. Testcase generation can continue.
        logger.warning(
            "[AGENTIC SCRIPTGEN] Could not load shared flow steps | "
            "ush_id=%s error=%s",
            user_story_hierarchy_id,
            str(exc),
        )

    combined_steps, flow_steps_count = (
        ScriptGenAdapter.prepend_flow_steps(
            flow_steps,
            list(payload.testcase_steps or []),
        )
    )

    # -----------------------------------------------------------------
    # Resolve repository configuration
    # -----------------------------------------------------------------
    try:
        repo_path: Any = DataSourceDAO.get_github_repo_config(
            db,
            tenant_id,
        )

        properties = (
            DataSourceDAO.get_latest_github_properties(
                db,
                tenant_id,
            )
            or {}
        )

        local_repo_path = str(
            properties.get("local_repo_path")
            or ""
        ).strip()

        if local_repo_path:
            from pathlib import Path

            from worktop.core_services.app.utility.github_rest_service_utility import (
                GitHubRestServiceUtility,
            )

            repo_dir = Path(local_repo_path)

            if (
                repo_dir.is_dir()
                and GitHubRestServiceUtility.is_git_repo(repo_dir)
            ):
                git_info = (
                    GitHubRestServiceUtility.extract_local_git_info(
                        repo_dir
                    )
                    or {}
                )

                if git_info.get("repo_path"):
                    repo_path["repo_path"] = git_info["repo_path"]

                if git_info.get("branch_name"):
                    repo_path["branch_name"] = git_info[
                        "branch_name"
                    ]

                repo_path["repo_dir"] = str(repo_dir)

    except Exception as exc:
        logger.exception(
            "[AGENTIC SCRIPTGEN] Failed to resolve repository | "
            "job_id=%s",
            job_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve repository: {exc}",
        ) from exc

    # -----------------------------------------------------------------
    # Build GenerationRequest for GenerationOrchestrator
    # -----------------------------------------------------------------
    try:
        generation_request = (
            ScriptGenAdapter.to_generation_request(
                job_id=job_id,
                repo_path=repo_path,
                tenant_id=tenant_id,
                testcase_id=testcase_id,
                automation_steps=combined_steps,
                branch=None,
                run_validation=payload.run_validation,
                testcase_name=testcase_name,
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # -----------------------------------------------------------------
    # Create job tracking record
    # -----------------------------------------------------------------
    generation_job_store.create(
        job_id=job_id,
        user_story_hierarchy_id=user_story_hierarchy_id,
        testcase_id=testcase_id,
        tenant_id=int(tenant_id),
        user_story_id=user_story_id,
        row_id=row_id,
        testcase_name=testcase_name,
        requested_by=requested_by,
        automation_steps_count=len(
            payload.testcase_steps or []
        ),
        flow_steps_count=flow_steps_count,
        metadata={
            "repo_path": repo_path,
            "combined_steps_count": len(combined_steps),
            "worker_type": "agentic",
        },
    )

    # -----------------------------------------------------------------
    # Existing queue still receives the original 3-item contract:
    #
    # (
    #     user_story_hierarchy_id,
    #     testcase_id,
    #     request_data_dict,
    # )
    # -----------------------------------------------------------------
    request_data_dict: dict[str, Any] = {
        # This is the only value needed for worker dispatch.
        "worker_type": "agentic",

        "job_id": job_id,
        "tenant_id": int(tenant_id),
        "user_story_id": user_story_id,
        "row_id": row_id,
        "user_name": requested_by,
        "requested_by": requested_by,
        "testcase_name": testcase_name,

        # New GenerationOrchestrator input.
        "generation_request": generation_request.model_dump(
            mode="json"
        ),

        # Used while adapting GenerationResult to existing SSE output.
        "flow_steps_count": flow_steps_count,
        "automation_steps_count": len(
            payload.testcase_steps or []
        ),
        "combined_steps_count": len(combined_steps),
    }

    try:
        enqueue_scriptgen_task(
            user_story_hierarchy_id,
            testcase_id,
            request_data_dict,
        )

    except Exception as exc:
        generation_job_store.fail(
            job_id,
            exc,
        )

        logger.exception(
            "[AGENTIC SCRIPTGEN] Failed to enqueue generation | "
            "job_id=%s ush_id=%s testcase_id=%s",
            job_id,
            user_story_hierarchy_id,
            testcase_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue Playwright generation.",
        ) from exc

    logger.info(
        "[AGENTIC SCRIPTGEN] Generation queued | "
        "job_id=%s tenant_id=%s ush_id=%s testcase_id=%s "
        "flow_steps=%s testcase_steps=%s total_steps=%s",
        job_id,
        tenant_id,
        user_story_hierarchy_id,
        testcase_id,
        flow_steps_count,
        len(payload.testcase_steps or []),
        len(combined_steps),
    )

    return GenerationAcceptedResponse(
        job_id=job_id,
        status=JOB_QUEUED,
        testcase_id=testcase_id,
        user_story_hierarchy_id=user_story_hierarchy_id,
        automation_steps_count=len(
            payload.testcase_steps or []
        ),
        flow_steps_count=flow_steps_count,
    )