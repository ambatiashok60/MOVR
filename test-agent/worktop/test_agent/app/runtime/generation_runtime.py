from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from worktop.test_agent.app.llm.llm_client import LLMClient
from worktop.test_agent.app.llm.llm_client_factory import LLMClientFactory
from worktop.test_agent.app.schemas.generation_request import GenerationRequest


@dataclass(frozen=True)
class GenerationRuntime:
    job_id: str
    tenant_id: str | None
    repo_path: str
    branch: str | None
    db: Any | None
    llm_client: LLMClient

    @classmethod
    def from_request(
        cls,
        request: GenerationRequest,
        db: Any | None = None,
        llm_factory: LLMClientFactory | None = None,
    ) -> "GenerationRuntime":
        factory = llm_factory or LLMClientFactory()
        return cls(
            job_id=request.job_id,
            tenant_id=request.tenant_id,
            repo_path=request.repo_path,
            branch=request.branch,
            db=db,
            llm_client=factory.create(db=db, tenant_id=request.tenant_id),
        )
