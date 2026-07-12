from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

class AgentToolCall(BaseModel):
    id: str
    tool_name: Literal["read_file", "search_repository", "list_files"]
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str

class AgentFileChange(BaseModel):
    path: str
    status: Literal["added", "modified", "deleted"]
    new_content: str = ""
    rationale: str = ""
    evidence: list[str] = Field(default_factory=list)

class AgentTurn(BaseModel):
    status: Literal["needs_evidence", "ready_to_patch", "completed", "blocked"]
    reasoning_summary: str
    root_cause: str | None = None
    evidence: list[str] = Field(default_factory=list)
    tool_calls: list[AgentToolCall] = Field(default_factory=list)
    plan: dict[str, Any] = Field(default_factory=dict)
    file_changes: list[AgentFileChange] = Field(default_factory=list)
    final_summary: str | None = None

class ToolObservation(BaseModel):
    tool_call_id: str
    tool_name: str
    success: bool
    summary: str
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
