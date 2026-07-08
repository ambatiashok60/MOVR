from __future__ import annotations

from app.agents.base_agent import BaseAgent, log_exception, log_performance
from app.prompts.flow_merge_prompt import build_flow_merge_prompt
from app.schemas.flow_merge import FlowMergePlan
from app.schemas.functional_intent import FunctionalIntent


class FlowMergeAgent(BaseAgent):
    agent_name = "flow_merge_agent"

    @log_performance("flow_merge_agent.plan")
    def plan(self, intent: FunctionalIntent) -> FlowMergePlan:
        context = self.log_start("flow_merge")
        try:
            return self.complete_structured(
                prompt=build_flow_merge_prompt(intent),
                response_model=FlowMergePlan,
            )
        except Exception as exc:
            log_exception(exc, context=context)
            raise
