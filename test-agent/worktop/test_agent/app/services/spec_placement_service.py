from __future__ import annotations



from worktop.test_agent.app.agents.spec_placement_agent import SpecPlacementAgent
from worktop.test_agent.app.llm.llm_client import LLMClient
from worktop.test_agent.app.schemas.functional_intent import FunctionalIntent
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.repository_inventory import RepositoryInventory
from worktop.test_agent.app.schemas.spec_placement import SpecPlacementDecision
from worktop.core_services.app.utility.custom_logger.logging import logger



class SpecPlacementService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.agent = SpecPlacementAgent(llm_client=llm_client)

    def decide(
        self,
        inventory: RepositoryInventory,
        intent: FunctionalIntent | None = None,
        ui_context: PlaywrightUiContext | None = None,
    ) -> SpecPlacementDecision:
        logger.info(
            "[playwright-generation] stage=spec_placement status=started test_files=%s",
            len(inventory.test_files),
        )
        try:
            decision = self.agent.decide(inventory, intent, ui_context)
            logger.info(
                "[playwright-generation] stage=spec_placement status=completed target=%s create_new=%s confidence=%s",
                decision.target_spec_file,
                decision.create_new,
                decision.confidence,
            )
            logger.info(
                "[playwright-generation] stage=spec_placement decision=%s evidence=%s risk=%s fallback=%s",
                decision.decision_trace.decision,
                decision.decision_trace.evidence,
                decision.decision_trace.risk,
                decision.decision_trace.fallback,
            )
            return decision
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=spec_placement status=failed_using_fallback error=%s",
                exc,
            )
            decision = self.agent._fallback_decision(inventory)
            logger.info(
                "[playwright-generation] stage=spec_placement status=fallback_completed target=%s create_new=%s confidence=%s",
                decision.target_spec_file,
                decision.create_new,
                decision.confidence,
            )
            logger.info(
                "[playwright-generation] stage=spec_placement fallback_reason=%s evidence=%s",
                decision.decision_trace.justification,
                decision.decision_trace.evidence,
            )
            return decision
