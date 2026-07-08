from __future__ import annotations

from pydantic import BaseModel, Field


class LocatorDecision(BaseModel):
    locator: str
    source_evidence: list[str] = Field(default_factory=list)
    alternatives_rejected: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""


class LocatorDecisionSet(BaseModel):
    decisions: list[LocatorDecision] = Field(default_factory=list)
