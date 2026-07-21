from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateApiScenariosRequest(BaseModel):
    user_story_hierarchy_id: int
    user_story_id: str | None = None
    tenant_id: int | str | None = 1
    repo_path: str
    story_title: str | None = None
    story_description: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    additional_context: str | None = None
    branch: str | None = None
