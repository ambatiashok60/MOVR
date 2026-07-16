"""Frontend-facing request/response models for the Playwright generation API.

These are the public HTTP contract. The internal ``GenerationRequest`` is never
exposed directly: the caller does not know ``repo_path``, ``branch``,
``job_id`` or model-client details — those are resolved server-side.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlaywrightGenerationRequest(BaseModel):
    user_story_hierarchy_id: int
    testcase_id: str
    tenant_id: int | None = None
    testcase_steps: list[str] = Field(default_factory=list)
    additional_context: str | None = None
    user_story_id: str | None = None
    row_id: int | None = None
    run_validation: bool = True


class GenerationAcceptedResponse(BaseModel):
    job_id: str
    status: str
    testcase_id: str
    user_story_hierarchy_id: int
    automation_steps_count: int = 0
    flow_steps_count: int = 0


class GenerationAbortResponse(BaseModel):
    job_id: str
    status: str
    message: str | None = None
