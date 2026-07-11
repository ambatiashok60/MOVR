from __future__ import annotations

from pydantic import BaseModel, Field

from worktop.api_agent.app.schemas.source_context import DependencyCandidate


class MockStubPlan(BaseModel):
    strategy: str | None = None
    reused_helpers: list[str] = Field(default_factory=list)
    dependencies_to_mock: list[DependencyCandidate] = Field(default_factory=list)
    generated_stubs: list[str] = Field(default_factory=list)
    external_services_to_stub: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    approval_required: bool = False
    approval_reasons: list[str] = Field(default_factory=list)
    runtime_signals: list[str] = Field(default_factory=list)
    provisioning_actions: list[str] = Field(default_factory=list)
    auth_strategy: str | None = None
