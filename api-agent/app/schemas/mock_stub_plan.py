from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.source_context import DependencyCandidate


class MockStubPlan(BaseModel):
    strategy: str | None = None
    reused_helpers: list[str] = Field(default_factory=list)
    dependencies_to_mock: list[DependencyCandidate] = Field(default_factory=list)
    generated_stubs: list[str] = Field(default_factory=list)
    external_services_to_stub: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
