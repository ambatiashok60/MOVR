from __future__ import annotations

from app.agents.base_agent import BaseAgent, log_exception, log_performance, logger
from app.prompts.source_mapping_prompt import build_source_mapping_prompt
from app.schemas.functional_intent import FunctionalIntent
from app.schemas.source_intelligence import SourceIntelligence


class SourceMapperAgent(BaseAgent):
    agent_name = "source_mapper_agent"

    @log_performance("source_mapper_agent.map")
    def map(self, intent: FunctionalIntent) -> SourceIntelligence:
        context = self.log_start("source_mapping")
        try:
            source = self.complete_structured(
                prompt=build_source_mapping_prompt(intent),
                response_model=SourceIntelligence,
            )
            logger.info("Source mapping completed")
            return source
        except Exception as exc:
            log_exception(exc, context=context)
            raise
