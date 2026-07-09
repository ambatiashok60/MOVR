from __future__ import annotations

from app.agents.base_agent import BaseAgent, logger
from app.prompts.flow_merge_prompt import build_flow_merge_prompt
from app.schemas.behavioral_test_unit import ExistingTestContext
from app.schemas.flow_merge import FlowMergePlan
from app.schemas.functional_intent import FunctionalIntent


class FlowMergeAgent(BaseAgent):
    agent_name = "flow_merge_agent"

    def plan(
        self,
        intent: FunctionalIntent,
        existing_test_context: ExistingTestContext | None = None,
    ) -> FlowMergePlan:
        context = self.log_start("flow_merge")
        try:
            return self.complete_structured(
                prompt=build_flow_merge_prompt(intent, existing_test_context),
                response_model=FlowMergePlan,
            )
        except Exception as exc:
            logger.exception(
                "[playwright-generation] agent=%s stage=flow_merge status=failed context=%s error=%s",
                self.agent_name,
                context,
                exc,
            )
            raise
