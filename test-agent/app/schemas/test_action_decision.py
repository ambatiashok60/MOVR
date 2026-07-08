from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.decision_trace import DecisionTrace


class TestActionDecision(BaseModel):
    action: str
    target_test_title: str | None = None
    confidence: float = 0.0
    decision_trace: DecisionTrace = Field(
        default_factory=lambda: DecisionTrace(decision="undecided")
    )
