from __future__ import annotations

from pydantic import BaseModel, Field


class FunctionalIntent(BaseModel):
    capability: str = ""
    actor: str = ""
    journey: list[str] = Field(default_factory=list)
    state_transitions: list[str] = Field(default_factory=list)
    assertions: list[str] = Field(default_factory=list)
