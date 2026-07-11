from __future__ import annotations

import logging
from typing import Any

from app.llm.application.llm_client import LLMClient
from app.llm.infrastructure.default_llm_client_adapter import DefaultLLMClientAdapter
from app.llm.infrastructure.mock_llm_client import MockLLMClient
from app.utils.logging_utils import build_log_context, log_exception, log_step

logger = logging.getLogger("ai_workspace.llm_factory")


class LLMClientFactory:
    def create(self, db: Any | None, tenant_id: str | None, allow_mock: bool = False) -> LLMClient:
        if not tenant_id:
            raise RuntimeError("tenant_id is required to create the AI Workspace LLM client.")

        context = build_log_context(tenant_id=tenant_id, stage="llm_client_factory")
        log_step("ai_workspace_llm_client_factory_started", context)
        try:
            client = DefaultLLMClientAdapter(db=db, tenant_id=tenant_id)
            log_step("ai_workspace_llm_client_factory_completed", context)
            return client
        except Exception as exc:
            if allow_mock:
                logger.warning("Using explicit mock LLM client for AI Workspace", exc_info=True)
                return MockLLMClient()
            log_exception(exc, context=context)
            raise RuntimeError("Unable to create the real AI Workspace LLM client.") from exc
