from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.decision_trace import DecisionTrace


class SpecPlacementDecision(BaseModel):
    target_spec_file: str
    create_new: bool = False
    confidence: float = 0.0
    decision_trace: DecisionTrace = Field(
        default_factory=lambda: DecisionTrace(decision="undecided")
    )
