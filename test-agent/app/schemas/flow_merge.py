from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.decision_trace import DecisionTrace


class FlowMergePlan(BaseModel):
    stable_region: str = ""
    extension_region: str = ""
    preserved_steps: list[str] = Field(default_factory=list)
    added_steps: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    decision_trace: DecisionTrace = Field(
        default_factory=lambda: DecisionTrace(decision="undecided")
    )
