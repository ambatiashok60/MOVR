from __future__ import annotations

from typing import Any

from worktop.core_services.app.utility.custom_logger.log_helpers import (
    log_exception,
    log_step,
)
from worktop.core_services.app.utility.custom_logger.logging import logger

from app.llm.default_llm_client import DefaultLLMClientAdapter
from app.llm.llm_client import LLMClient


class LLMClientFactory:
    def create(self, db: Any | None, tenant_id: str | None) -> LLMClient:
        if not tenant_id:
            raise RuntimeError(
                "tenant_id is required to create the real LLM client for the "
                "agentic Playwright generation process."
            )

        log_step("llm_client_factory_started", {"tenant_id": tenant_id, "stage": "llm"})
        try:
            return DefaultLLMClientAdapter(db=db, tenant_id=tenant_id)
        except Exception as exc:
            log_exception(exc, context={"tenant_id": tenant_id, "stage": "llm_client_factory"})
            raise RuntimeError(
                "Unable to create the real LLM client for the agentic Playwright "
                "generation process."
            ) from exc
