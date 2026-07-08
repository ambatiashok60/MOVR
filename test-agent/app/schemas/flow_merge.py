from __future__ import annotations

from pydantic import BaseModel, Field


class FlowMergePlan(BaseModel):
    stable_region: str = ""
    extension_region: str = ""
    preserved_steps: list[str] = Field(default_factory=list)
    added_steps: list[str] = Field(default_factory=list)
