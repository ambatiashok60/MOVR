from __future__ import annotations

from app.agents.base_agent import BaseAgent, logger
from app.prompts.functional_intent_prompt import build_functional_intent_prompt
from app.schemas.functional_intent import FunctionalIntent
from app.schemas.generation_request import GenerationRequest


class FunctionalIntentAgent(BaseAgent):
    agent_name = "functional_intent_agent"

    def extract(self, request: GenerationRequest) -> FunctionalIntent:
        context = self.log_start("functional_intent", job_id=request.job_id)
        try:
            intent = self.complete_structured(
                prompt=build_functional_intent_prompt(request),
                response_model=FunctionalIntent,
            )
            logger.info("Functional intent extracted")
            return intent
        except Exception as exc:
            logger.exception(
                "[playwright-generation] agent=%s stage=functional_intent status=failed context=%s error=%s",
                self.agent_name,
                context,
                exc,
            )
            raise
