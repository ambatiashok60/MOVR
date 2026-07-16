from __future__ import annotations

from pydantic import BaseModel, Field


class TechnologyProfile(BaseModel):
    framework: str | None = None
    api_patterns: list[str] = Field(default_factory=list)
    mock_patterns: list[str] = Field(default_factory=list)
    auth_strategy: str | None = None
    component_libraries: list[str] = Field(default_factory=list)
    state_management: list[str] = Field(default_factory=list)
