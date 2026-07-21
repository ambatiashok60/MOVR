from typing import Literal

from pydantic import BaseModel, Field


class WorkspaceRequest(BaseModel):
    path: str


class ChatRequest(WorkspaceRequest):
    message: str = Field(min_length=1, max_length=50_000)
    files: list[str] = Field(default_factory=list, max_length=30)
    detail: Literal["auto", "brief", "detailed"] = "auto"
    session_id: str | None = None


class FileChange(BaseModel):
    path: str
    content: str | None = None
    operation: Literal["create", "update", "delete"]
    original_sha256: str | None = None

class RelationshipEvidence(BaseModel):
    source: str
    line: int
    text: str
    relation: str


class ProposalRequest(WorkspaceRequest):
    changes: list[FileChange] = Field(min_length=1, max_length=100)


class ApplyRequest(BaseModel):
    proposal_id: str
    accepted_paths: list[str]
    accepted_hunks: dict[str, list[str]] = Field(default_factory=dict)


class ActionRequest(BaseModel):
    action_id: str


class CommandRequest(WorkspaceRequest):
    command: list[str] = Field(min_length=1, max_length=20)
    timeout_seconds: int = Field(default=60, ge=1, le=300)
