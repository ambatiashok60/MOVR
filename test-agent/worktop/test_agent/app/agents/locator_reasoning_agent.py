from __future__ import annotations

from worktop.test_agent.app.agents.base_agent import BaseAgent
from worktop.core_services.app.utility.custom_logger.logging import logger
from worktop.test_agent.app.prompts.locator_reasoning_prompt import build_locator_reasoning_prompt
from worktop.test_agent.app.schemas.locator_decision import LocatorDecision, LocatorDecisionSet
from worktop.test_agent.app.schemas.source_intelligence import SourceIntelligence
from worktop.test_agent.app.schemas.behavioral_test_unit import AnchorFlowContext
from worktop.test_agent.app.schemas.functional_intent import FunctionalIntent
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.test_action_decision import TestActionDecision


class LocatorReasoningAgent(BaseAgent):
    agent_name = "locator_reasoning_agent"

    def decide(
        self,
        source: SourceIntelligence,
        action: TestActionDecision | None = None,
        anchor: AnchorFlowContext | None = None,
        intent: FunctionalIntent | None = None,
        ui_context: PlaywrightUiContext | None = None,
    ) -> list[LocatorDecision]:
        context = self.log_start("locator_reasoning")
        try:
            decisions = self.complete_structured(
                prompt=build_locator_reasoning_prompt(
                    source, action, anchor, intent, ui_context
                ),
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
