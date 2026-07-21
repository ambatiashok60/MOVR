from __future__ import annotations

from typing import Any

from worktop.api_agent.app.llm.llm_client import LLMClient
from worktop.api_agent.app.llm.local_fallback_client import LocalFallbackLLMClient
from worktop.api_agent.app.llm.worktop_model_client_adapter import WorktopModelClientAdapter
from worktop.api_agent.app.utils.logging_utils import log_exception, log_step


class LLMClientFactory:
    def create(
        self,
        db: Any | None,
        tenant_id: int | str | None,
        allow_local_fallback: bool = True,
    ) -> LLMClient:
        if tenant_id is None:
            raise RuntimeError("tenant_id is required to create an API generation LLM client")

        log_step(
            "api_agent_llm_client_factory_started",
            {"tenant_id": tenant_id, "stage": "llm_client_factory"},
        )
        try:
            return WorktopModelClientAdapter(db=db, tenant_id=tenant_id)
        except Exception as exc:
            log_exception(
                exc,
                context={"tenant_id": tenant_id, "stage": "api_agent_llm_client_factory"},
            )
            if not allow_local_fallback:
                raise
            return LocalFallbackLLMClient()
