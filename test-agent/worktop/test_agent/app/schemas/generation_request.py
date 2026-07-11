from __future__ import annotations

from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    job_id: str
    repo_path: str
    branch: str | None = None
    tenant_id: str | None = None
    test_case_name: str
    steps: list[str] = Field(default_factory=list)
    run_validation: bool = True
