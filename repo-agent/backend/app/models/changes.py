"""File change records and validation results."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FileChange(BaseModel):
    path: str
    change_type: str  # created | modified | deleted | moved
    before_hash: str | None = None
    after_hash: str | None = None
    diff: str = ""
    plan_step_id: str | None = None
    tool_call_id: str | None = None
    proposal_only: bool = False


class ValidationResult(BaseModel):
    name: str
    command: list[str] = Field(default_factory=list)
    status: str  # passed | failed | skipped
    exit_code: int | None = None
    summary: str = ""
    output_excerpt: str | None = None
    duration_ms: int = 0
