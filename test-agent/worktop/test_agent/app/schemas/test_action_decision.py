from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from worktop.test_agent.app.schemas.decision_trace import DecisionTrace


class TestActions:
    """Canonical test-action values shared across agents, services, and guards."""

    EXTEND_EXISTING_TEST = "extend_existing_test"
    APPEND_NEW_TEST = "append_new_test"
    CREATE_NEW_SPEC = "create_new_spec"


TestActionValue = Literal["extend_existing_test", "append_new_test", "create_new_spec"]


class TestActionDecision(BaseModel):
    action: TestActionValue
    target_test_title: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    decision_trace: DecisionTrace = Field(
        default_factory=lambda: DecisionTrace(decision="undecided")
    )
