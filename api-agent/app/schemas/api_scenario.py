from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.execution_target import ExecutionTarget


class ApiScenario(BaseModel):
    api_scenario_id: str
    scenario_name: str
    scenario_type: str = Field(description="positive, negative, contract, auth, edge, etc.")
    service_name: str | None = None
    method: str | None = None
    endpoint: str | None = None
    priority: str = "medium"
    execution_target: ExecutionTarget = ExecutionTarget.CI
    reason: str
    scenario_steps: list[str] = Field(default_factory=list)
    assertions: list[str] = Field(default_factory=list)
