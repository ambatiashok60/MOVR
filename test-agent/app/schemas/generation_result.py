from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.coverage import CoveragePreservationReport
from app.schemas.decision_trace import DecisionTrace
from app.schemas.repo_profile import RepoProfile
from app.schemas.validation_result import ValidationResult


class GenerationResult(BaseModel):
    job_id: str
    files_changed: list[str] = Field(default_factory=list)
    diff_summary: str = ""
    diff: str = ""
    confidence: float = 0.0
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    repo_profile: RepoProfile | None = None
    decision_trace: list[DecisionTrace] = Field(default_factory=list)
    validation: ValidationResult | None = None
    coverage: CoveragePreservationReport | None = None
