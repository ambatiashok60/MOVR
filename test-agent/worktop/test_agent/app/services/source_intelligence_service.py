from __future__ import annotations



from worktop.test_agent.app.agents.source_mapper_agent import SourceMapperAgent
from worktop.test_agent.app.llm.llm_client import LLMClient
from worktop.test_agent.app.schemas.functional_intent import FunctionalIntent
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.source_intelligence import SourceIntelligence
from worktop.test_agent.utils.logging import get_logger

logger = get_logger(__name__)


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
