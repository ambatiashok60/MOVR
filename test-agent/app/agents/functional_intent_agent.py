from __future__ import annotations

from app.agents.base_agent import BaseAgent, log_exception, log_performance, logger
from app.prompts.functional_intent_prompt import build_functional_intent_prompt
from app.schemas.functional_intent import FunctionalIntent
from app.schemas.generation_request import GenerationRequest


class FunctionalIntentAgent(BaseAgent):
    agent_name = "functional_intent_agent"

    @log_performance("functional_intent_agent.extract")
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
            log_exception(exc, context=context)
            raise
