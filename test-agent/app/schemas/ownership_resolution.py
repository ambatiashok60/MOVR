from __future__ import annotations

from pydantic import BaseModel, Field


class OwnershipResolution(BaseModel):
    owner_path: str
    owner_kind: str
    artifacts: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""
