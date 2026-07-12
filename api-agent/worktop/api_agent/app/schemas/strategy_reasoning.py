from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RejectedStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy_name: str
    reason: str
    incompatible_capabilities: list[str] = Field(default_factory=list)


class StrategyReasoningOutput(BaseModel):
    """Hardened LLM review of a deterministic capability-composed plan."""

    model_config = ConfigDict(extra="forbid")
    decision: Literal["confirm", "needs_more_evidence", "needs_review", "unsupported"]
    selected_strategy: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(min_length=1)
    rejected_alternatives: list[RejectedStrategy] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    recommended_next_stage: Literal["strategy_composition", "targeted_discovery", "dependency_planning", "review", "unsupported"]

