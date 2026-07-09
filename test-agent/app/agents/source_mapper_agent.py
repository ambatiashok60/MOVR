from __future__ import annotations

from app.agents.base_agent import BaseAgent, logger
from app.prompts.source_mapping_prompt import build_source_mapping_prompt
from app.schemas.functional_intent import FunctionalIntent
from app.schemas.playwright_ui_context import PlaywrightUiContext
from app.schemas.source_intelligence import SourceIntelligence


class SourceMapperAgent(BaseAgent):
    agent_name = "source_mapper_agent"

    def map(
        self,
        intent: FunctionalIntent,
        ui_context: PlaywrightUiContext | None = None,
    ) -> SourceIntelligence:
        context = self.log_start("source_mapping")
        try:
            source = self.complete_structured(
                prompt=build_source_mapping_prompt(intent, ui_context),
                response_model=SourceIntelligence,
            )
            logger.info("Source mapping completed")
            return source
        except Exception as exc:
            logger.exception(
                "[playwright-generation] agent=%s stage=source_mapping status=failed context=%s error=%s",
                self.agent_name,
                context,
                exc,
            )
            raise
