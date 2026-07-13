from typing import Literal

from pydantic import BaseModel, Field


class WorkspaceRequest(BaseModel):
    path: str


class ChatRequest(WorkspaceRequest):
    message: str = Field(min_length=1, max_length=50_000)
    files: list[str] = Field(default_factory=list, max_length=30)


class FileChange(BaseModel):
    path: str
    content: str | None = None
    operation: Literal["create", "update", "delete"]
    original_sha256: str | None = None


class ProposalRequest(WorkspaceRequest):
    changes: list[FileChange] = Field(min_length=1, max_length=100)


class ApplyRequest(BaseModel):
    proposal_id: str
    accepted_paths: list[str]


class ActionRequest(BaseModel):
    action_id: str
