from fastapi import APIRouter, Depends, HTTPException

from app.ai_workspace.application.review.review_service import ReviewService
from app.ai_workspace.application.workspace_runtime_service import WorkspaceRuntimeService
from app.ai_workspace.domain.execution_context import ExecutionContext
from app.ai_workspace.domain.review_decision import ReviewDecision
from app.ai_workspace.dto.mappers import file_change_to_dto
from app.ai_workspace.dto.review_dto import ApplyChangesRequest, ApplyChangesResponse, FileChangeDto, ReviewDecisionRequest
from app.common.tenancy import get_tenant_id
from app.dependencies.ai_workspace_dependencies import (
    get_execution_by_id,
    get_review_service,
    get_workspace_runtime_service,
)

router = APIRouter(prefix="/ai-workspace/agent", tags=["Review"])


@router.get("/runs/{execution_id}/files", response_model=list[FileChangeDto])
def get_review(execution_id: str, review_service: ReviewService = Depends(get_review_service)) -> list[FileChangeDto]:
    return [file_change_to_dto(f) for f in review_service.get_changes(execution_id)]


@router.get("/runs/{execution_id}/review-summary")
def get_review_summary(execution_id: str, review_service: ReviewService = Depends(get_review_service)) -> dict:
    changes = review_service.get_changes(execution_id)
    kept = sum(1 for change in changes if change.decision.value == "kept")
    rejected = sum(1 for change in changes if change.decision.value == "rejected")
    pending = sum(1 for change in changes if change.decision.value == "pending")
    return {
        "runId": execution_id,
        "totalFiles": len(changes),
        "keptCount": kept,
        "rejectedCount": rejected,
        "pendingCount": pending,
    }


@router.post("/review/keep")
def keep_file(request: ReviewDecisionRequest, review_service: ReviewService = Depends(get_review_service)) -> dict:
    review_service.set_decision(request.run_id, request.file_id, ReviewDecision.KEPT)
    return {"ok": True}


@router.post("/review/reject")
def reject_file(request: ReviewDecisionRequest, review_service: ReviewService = Depends(get_review_service)) -> dict:
    review_service.set_decision(request.run_id, request.file_id, ReviewDecision.REJECTED)
    return {"ok": True}


@router.post("/apply", response_model=ApplyChangesResponse)
def apply_changes(
    request: ApplyChangesRequest,
    review_service: ReviewService = Depends(get_review_service),
    runtime_service: WorkspaceRuntimeService = Depends(get_workspace_runtime_service),
    tenant_id: str = Depends(get_tenant_id),
) -> ApplyChangesResponse:
    # run_id == execution_id (see agent_service.py, which sets FileChange.run_id to
    # execution.execution_id) — resolving workspace_path this way means the frontend never
    # needs to send workspace_path itself on Apply, only run_id + kept_file_ids, matching the
    # server-staged Apply flow documented in ai-workspace/frontend/README.md.
    execution: ExecutionContext | None = get_execution_by_id(request.run_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Run not found")

    runtime = runtime_service.get(execution.session_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="No active workspace runtime for this run's session")

    applied_paths = review_service.apply(request.run_id, runtime.workspace_path, tenant_id, request.kept_file_ids)
    return ApplyChangesResponse(applied_file_paths=applied_paths)
