from __future__ import annotations

from pydantic import BaseModel, Field

from worktop.api_agent.app.schemas.coverage import ApiCoverageReport
from worktop.api_agent.app.schemas.review_report import ApiReviewReport
from worktop.api_agent.app.schemas.traceability import TraceabilityMatrix
from worktop.api_agent.app.schemas.generated_file import GeneratedFile
from worktop.api_agent.app.schemas.generation_manifest import GenerationManifest
from worktop.api_agent.app.schemas.mock_stub_plan import MockStubPlan
from worktop.api_agent.app.schemas.source_context import ExistingTestExample, SourceSnippet
from worktop.api_agent.app.schemas.validation_result import ValidationResult


class ApiTestGenerationResult(BaseModel):
    task_id: str
    user_story_hierarchy_id: int
    api_scenario_id: str
    generated_files: list[GeneratedFile] = Field(default_factory=list)
    validation: ValidationResult | None = None
    summary: str
    strategy_name: str | None = None
    strategy_confidence: str | None = None
    strategy_reasons: list[str] = Field(default_factory=list)
    reused_examples: list[ExistingTestExample] = Field(default_factory=list)
    source_files_used: list[SourceSnippet] = Field(default_factory=list)
    mock_stub_plan: MockStubPlan | None = None
    warnings: list[str] = Field(default_factory=list)
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    coverage: ApiCoverageReport | None = None
    traceability: TraceabilityMatrix | None = None
    review_report: ApiReviewReport | None = None
    manifest: GenerationManifest | None = None
