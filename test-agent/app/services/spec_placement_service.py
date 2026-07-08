from __future__ import annotations

from typing import Any

from worktop.core_services.app.utility.custom_logger.log_helpers import (
    log_card_simple,
    log_exception,
    log_metric,
    log_step,
)
from worktop.core_services.app.utility.custom_logger.logging import (
    log_performance,
    logger,
)

from app.agents.spec_placement_agent import SpecPlacementAgent
from app.llm.llm_client import LLMClient
from app.schemas.functional_intent import FunctionalIntent
from app.schemas.playwright_ui_context import PlaywrightUiContext
from app.schemas.repository_inventory import RepositoryInventory
from app.schemas.spec_placement import SpecPlacementDecision


class SpecPlacementService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.agent = SpecPlacementAgent(llm_client=llm_client)

    @log_performance("spec_placement_service.decide")
    def decide(
        self,
        inventory: RepositoryInventory,
        intent: FunctionalIntent | None = None,
        ui_context: PlaywrightUiContext | None = None,
    ) -> SpecPlacementDecision:
        log_step("spec_placement_service_started", {})
        try:
            decision = self.agent.decide(inventory, intent, ui_context)
            log_card_simple(
                title="Spec Placement Decision",
                message=f"Selected {decision.target_spec_file}",
                metadata={"confidence": decision.confidence, "decision": decision.model_dump()},
            )
            return decision
        except Exception as exc:
            log_exception(exc, context={"stage": "spec_placement"})
            raise
