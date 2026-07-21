from __future__ import annotations

from typing import Any

from worktop.test_agent.app.llm.default_llm_client import DefaultLLMClientAdapter
from worktop.test_agent.app.llm.llm_client import LLMClient
from worktop.core_services.app.utility.custom_logger.logging import logger



class LLMClientFactory:
    def create(self, db: Any | None, tenant_id: str | None) -> LLMClient:
        if not tenant_id:
            raise RuntimeError(
                "tenant_id is required to create the real LLM client for the "
                "agentic Playwright generation process."
            )

        logger.info(
            "[playwright-generation] stage=llm_client_factory status=started tenant_id=%s",
            tenant_id,
        )
        try:
            client = DefaultLLMClientAdapter(db=db, tenant_id=tenant_id)
            logger.info(
                "[playwright-generation] stage=llm_client_factory status=completed tenant_id=%s",
                tenant_id,
            )
            return client
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=llm_client_factory status=failed tenant_id=%s error=%s",
                tenant_id,
                exc,
            )
            raise RuntimeError(
                "Unable to create the real LLM client for the agentic Playwright "
                "generation process."
            ) from exc
