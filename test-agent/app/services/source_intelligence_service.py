from __future__ import annotations

import logging


from app.agents.source_mapper_agent import SourceMapperAgent
from app.llm.llm_client import LLMClient
from app.schemas.functional_intent import FunctionalIntent
from app.schemas.playwright_ui_context import PlaywrightUiContext
from app.schemas.source_intelligence import SourceIntelligence

logger = logging.getLogger(__name__)


class SourceIntelligenceService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.agent = SourceMapperAgent(llm_client=llm_client)

    def map(
        self,
        intent: FunctionalIntent,
        ui_context: PlaywrightUiContext | None = None,
    ) -> SourceIntelligence:
        logger.info(
            "[playwright-generation] stage=source_intelligence status=started capability=%s",
            intent.capability,
        )
        try:
            source = self.agent.map(intent, ui_context)
            logger.info(
                "[playwright-generation] stage=source_intelligence status=completed components=%s locators=%s",
                len(source.components),
                len(source.locator_evidence),
            )
            return source
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=source_intelligence status=failed error=%s",
                exc,
            )
            raise
