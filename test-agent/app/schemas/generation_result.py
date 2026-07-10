from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.coverage import CoveragePreservationReport
from app.schemas.decision_trace import DecisionTrace
from app.schemas.generation_budget import BudgetReport
from app.schemas.generation_manifest import GenerationManifest
from app.schemas.repo_profile import RepoProfile
from app.schemas.review_report import ReviewReport
from app.schemas.test_value import TestValueReport
from app.schemas.traceability import TraceabilityMatrix
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
    test_value: TestValueReport | None = None
    traceability: TraceabilityMatrix | None = None
    review_report: ReviewReport | None = None
    manifest: GenerationManifest | None = None
    budget: BudgetReport | None = None
    idempotent_replay: bool = False
    replayed_from_job: str | None = None
    generation_fingerprint: str = ""
