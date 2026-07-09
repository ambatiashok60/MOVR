from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.api_scenario import ApiScenario


class ApiScenarioGenerationResult(BaseModel):
    task_id: str
    user_story_hierarchy_id: int
    user_story_id: str | None = None
    scenarios: list[ApiScenario] = Field(default_factory=list)
    repo_findings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
