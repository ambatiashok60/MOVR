from __future__ import annotations

from app.agents.base_agent import BaseAgent, logger
from app.prompts.locator_reasoning_prompt import build_locator_reasoning_prompt
from app.schemas.locator_decision import LocatorDecision, LocatorDecisionSet
from app.schemas.source_intelligence import SourceIntelligence


class LocatorReasoningAgent(BaseAgent):
    agent_name = "locator_reasoning_agent"

    def decide(self, source: SourceIntelligence) -> list[LocatorDecision]:
        context = self.log_start("locator_reasoning")
        try:
            decisions = self.complete_structured(
                prompt=build_locator_reasoning_prompt(source),
                response_model=LocatorDecisionSet,
            )
            return decisions.decisions
        except Exception as exc:
            logger.exception(
                "[playwright-generation] agent=%s stage=locator_reasoning status=failed context=%s error=%s",
                self.agent_name,
                context,
                exc,
            )
            raise
