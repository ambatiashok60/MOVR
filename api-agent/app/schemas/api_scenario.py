from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.execution_target import ExecutionTarget

ScenarioType = Literal["positive", "negative", "contract", "auth", "edge"]
ScenarioPriority = Literal["high", "medium", "low"]
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class ApiScenario(BaseModel):
    api_scenario_id: str
    scenario_name: str
    scenario_type: ScenarioType
    service_name: str | None = None
    method: HttpMethod | None = None
    endpoint: str | None = None
    priority: ScenarioPriority = "medium"
    execution_target: ExecutionTarget = ExecutionTarget.CI
    reason: str
    scenario_steps: list[str] = Field(default_factory=list)
    assertions: list[str] = Field(default_factory=list)
