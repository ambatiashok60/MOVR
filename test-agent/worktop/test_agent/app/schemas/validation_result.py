from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationCheck(BaseModel):
    name: str
    passed: bool
    output: str = ""


class ValidationResult(BaseModel):
    passed: bool = False
    checks: list[ValidationCheck] = Field(default_factory=list)
    repair_attempted: bool = False
