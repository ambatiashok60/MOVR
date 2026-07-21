from __future__ import annotations

from pydantic import BaseModel, Field


class DependencySubstitution(BaseModel):
    dependency_capability: str
    mechanism: str
    source: str
    confidence: float = Field(ge=0.0, le=1.0)
    approval_required: bool = False
    reasons: list[str] = Field(default_factory=list)


class StrategyCandidate(BaseModel):
    strategy_name: str
    compatible: bool
    confidence: float = Field(ge=0.0, le=1.0)
    required_capabilities: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TestGenerationPlan(BaseModel):
    status: str = "needs_review"
    bootstrap: str | None = None
    inbound_driver: str | None = None
    reactive_model: str | None = None
    dependency_substitutions: list[DependencySubstitution] = Field(default_factory=list)
    fixture_strategy: str | None = None
    assertion_strategy: str | None = None
    cleanup_strategy: str | None = None
    validation_commands: list[str] = Field(default_factory=list)
    selected_strategy: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    candidates: list[StrategyCandidate] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)
