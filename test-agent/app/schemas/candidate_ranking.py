from __future__ import annotations

from pydantic import BaseModel, Field


class RankedCandidateRef(BaseModel):
    file_path: str
    test_title: str
    start_line: int | None = None
    relevance: float = Field(ge=0.0, le=1.0, default=0.0)
    reason: str = ""


class CandidateRanking(BaseModel):
    ranked: list[RankedCandidateRef] = Field(default_factory=list)
