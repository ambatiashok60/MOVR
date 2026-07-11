from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from worktop.api_agent.app.llm.llm_client import LLMClient
from worktop.api_agent.app.llm.model_client_factory import LLMClientFactory


@dataclass(frozen=True)
class GenerationRuntime:
    task_id: str
    tenant_id: int | str | None
    repo_path: str
    branch: str | None
    db: Any | None
    llm_client: LLMClient

    @classmethod
    def create(
        cls,
        task_id: str,
        tenant_id: int | str | None,
        repo_path: str,
        branch: str | None = None,
        db: Any | None = None,
        llm_factory: LLMClientFactory | None = None,
    ) -> "GenerationRuntime":
        factory = llm_factory or LLMClientFactory()
        return cls(
            task_id=task_id,
            tenant_id=tenant_id,
            repo_path=repo_path,
            branch=branch,
            db=db,
            llm_client=factory.create(db=db, tenant_id=tenant_id),
        )
