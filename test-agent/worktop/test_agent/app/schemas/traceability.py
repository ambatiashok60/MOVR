from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RequirementKind = Literal["step", "assertion"]
RequirementStatus = Literal["covered", "missing"]
CoverageSource = Literal["generated", "existing_flow"]


class RequirementTrace(BaseModel):
    """One requirement mapped to the code that implements it (or to nothing)."""

    requirement: str
    kind: RequirementKind
    status: RequirementStatus
    source: CoverageSource | None = None
    covered_by: str | None = None
    evidence: str = ""
    match_score: float = Field(ge=0.0, le=1.0, default=0.0)


class TraceabilityMatrix(BaseModel):
    """Requirement → coverage → code → source mapping for one generation run."""

    requirements: list[RequirementTrace] = Field(default_factory=list)
    covered: int = 0
    generated: int = 0
    reused: int = 0
    missing: int = 0
    complete: bool = True
    summary: list[str] = Field(default_factory=list)
