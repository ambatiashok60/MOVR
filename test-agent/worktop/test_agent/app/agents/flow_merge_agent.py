from __future__ import annotations

from worktop.test_agent.app.agents.base_agent import BaseAgent
from worktop.core_services.app.utility.custom_logger.logging import logger
from worktop.test_agent.app.prompts.flow_merge_prompt import build_flow_merge_prompt
from worktop.test_agent.app.schemas.behavioral_test_unit import ExistingTestContext
from worktop.test_agent.app.schemas.flow_merge import FlowMergePlan
from worktop.test_agent.app.schemas.functional_intent import FunctionalIntent


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
