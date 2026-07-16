from __future__ import annotations

from pydantic import BaseModel, Field

from worktop.test_agent.app.schemas.decision_trace import DecisionTrace


class OwnershipResolution(BaseModel):
    owner_path: str
    owner_kind: str
    create_new: bool = False
    artifacts: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    reason: str = ""
    decision_trace: DecisionTrace = Field(
        default_factory=lambda: DecisionTrace(decision="undecided")
    )
