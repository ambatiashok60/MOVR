"""Workspace validation endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.workspace.repository_detector import detect_repository
from app.workspace.workspace_manager import WorkspaceError, WorkspaceManager

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])
_manager = WorkspaceManager()


class WorkspaceValidateRequest(BaseModel):
    workspace_path: str


class WorkspaceValidateResponse(BaseModel):
    valid: bool
    resolved_path: str | None = None
    repository: dict | None = None
    error: str | None = None


@router.post("/validate", response_model=WorkspaceValidateResponse)
def validate_workspace(body: WorkspaceValidateRequest) -> WorkspaceValidateResponse:
    try:
        workspace = _manager.open_workspace(body.workspace_path)
    except WorkspaceError as exc:
        return WorkspaceValidateResponse(valid=False, error=str(exc))
    return WorkspaceValidateResponse(
        valid=True, resolved_path=str(workspace), repository=detect_repository(workspace)
    )
