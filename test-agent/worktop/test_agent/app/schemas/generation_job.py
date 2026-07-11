from __future__ import annotations

from pydantic import BaseModel, Field

from worktop.test_agent.app.schemas.generation_result import GenerationResult


class GenerationJob(BaseModel):
    job_id: str
    status: str
    result: GenerationResult | None = None
    events: list[str] = Field(default_factory=list)
