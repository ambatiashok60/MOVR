from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    passed: bool
    command: str | None = None
    summary: str
    details: list[str] = Field(default_factory=list)
