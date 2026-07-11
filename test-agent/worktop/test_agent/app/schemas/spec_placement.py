from __future__ import annotations

from pydantic import BaseModel, Field

from worktop.test_agent.app.schemas.decision_trace import DecisionTrace


class SpecPlacementDecisions:
    """Canonical decision labels used in spec-placement decision traces."""

    CREATE_NEW_SPEC = "create_new_spec"
    EXTEND_EXISTING_SPEC = "extend_existing_spec"


class SpecPlacementDecision(BaseModel):
    target_spec_file: str
    create_new: bool = False
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    decision_trace: DecisionTrace = Field(
        default_factory=lambda: DecisionTrace(decision="undecided")
    )
