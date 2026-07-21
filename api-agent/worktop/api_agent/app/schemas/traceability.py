from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RequirementKind = Literal["criterion", "step", "assertion"]
RequirementStatus = Literal["covered", "missing"]
CoverageSource = Literal["scenario", "generated_file"]


class RequirementTrace(BaseModel):
    """One requirement mapped to the scenario or code that implements it."""

    requirement: str
    kind: RequirementKind
    status: RequirementStatus
    source: CoverageSource | None = None
    covered_by: str | None = None
    evidence: str = ""
    match_score: float = Field(ge=0.0, le=1.0, default=0.0)


class TraceabilityMatrix(BaseModel):
    """Requirement → coverage → artifact mapping for one generation run."""

    requirements: list[RequirementTrace] = Field(default_factory=list)
    covered: int = 0
    missing: int = 0
    complete: bool = True
    summary: list[str] = Field(default_factory=list)
