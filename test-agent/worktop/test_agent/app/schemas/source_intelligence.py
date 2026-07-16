from __future__ import annotations

from pydantic import BaseModel, Field


class SourceEvidence(BaseModel):
    path: str
    symbol: str | None = None
    reason: str = ""


class SourceIntelligence(BaseModel):
    routes: list[SourceEvidence] = Field(default_factory=list)
    components: list[SourceEvidence] = Field(default_factory=list)
    services: list[SourceEvidence] = Field(default_factory=list)
    locator_evidence: list[SourceEvidence] = Field(default_factory=list)
