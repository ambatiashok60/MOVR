from __future__ import annotations

from typing import Any

from worktop.core_services.app.utility.custom_logger.log_helpers import (
    log_card_simple,
    log_exception,
    log_metric,
    log_step,
)
from worktop.core_services.app.utility.custom_logger.logging import (
    log_performance,
    logger,
)

from app.agents.source_mapper_agent import SourceMapperAgent
from app.llm.llm_client import LLMClient
from app.schemas.functional_intent import FunctionalIntent
from app.schemas.source_intelligence import SourceIntelligence


class SourceIntelligenceService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.agent = SourceMapperAgent(llm_client=llm_client)

    @log_performance("source_intelligence_service.map")
    def map(self, intent: FunctionalIntent) -> SourceIntelligence:
        log_step("source_intelligence_started", {"capability": intent.capability})
        try:
            return self.agent.map(intent)
        except Exception as exc:
            log_exception(exc, context={"stage": "source_intelligence"})
            raise
