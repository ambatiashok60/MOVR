from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DecisionAlternative(BaseModel):
    decision: str
    reason_rejected: str


class DecisionTrace(BaseModel):
    decision: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    justification: str = ""
    evidence: list[str] = Field(default_factory=list)
    alternatives: list[DecisionAlternative] = Field(default_factory=list)
    risk: str = "unknown"
    fallback: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
