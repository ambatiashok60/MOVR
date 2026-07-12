from __future__ import annotations

from worktop.test_agent.app.agents.base_agent import BaseAgent
from worktop.core_services.app.utility.custom_logger.logging import logger
from worktop.test_agent.app.prompts.spec_placement_prompt import build_spec_placement_prompt
from worktop.test_agent.app.schemas.decision_trace import DecisionTrace
from worktop.test_agent.app.schemas.exploration import SpecPlacementTurn
from worktop.test_agent.app.schemas.functional_intent import FunctionalIntent
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.repository_inventory import RepositoryInventory
from worktop.test_agent.app.schemas.spec_placement import SpecPlacementDecision, SpecPlacementDecisions


class SpecPlacementAgent(BaseAgent):
    agent_name = "spec_placement_agent"

    def decide(
        self,
        inventory: RepositoryInventory,
        intent: FunctionalIntent | None = None,
        ui_context: PlaywrightUiContext | None = None,
    ) -> SpecPlacementDecision:
        context = self.log_start("spec_placement")
        try:
            prompt = build_spec_placement_prompt(
                inventory=inventory,
                intent=intent,
                ui_context=ui_context,
                include_contract=False,
            )
            prompt += (
                "\n\nBefore deciding, READ the most promising candidate spec files "
                "to confirm which one truly owns this business behavior — do not "
                "decide from file names alone. State your reasoning each turn and "
                "give a reason for every file you request."
            )
            decision = self.complete_with_exploration(
                prompt, SpecPlacementTurn, inventory.repo_path
            )
            self.log_decision(
                "Spec Placement Decision",
                f"Selected {decision.target_spec_file}",
                confidence=decision.confidence,
                decision="create_new" if decision.create_new else "extend_existing",
            )
            logger.info("Spec placement decision completed")
            return decision
        except Exception as exc:
            logger.exception(
                "[playwright-generation] agent=%s stage=spec_placement status=failed context=%s error=%s",
                self.agent_name,
                context,
                exc,
            )
            raise

    def _fallback_decision(
        self,
        inventory: RepositoryInventory,
    ) -> SpecPlacementDecision:
        target = (
            inventory.test_files[0].path
            if inventory.test_files
            else "tests/generated.spec.ts"
        )
        create_new = not inventory.test_files
        return SpecPlacementDecision(
            target_spec_file=target,
            create_new=create_new,
            confidence=0.35,
            decision_trace=DecisionTrace(
                decision=SpecPlacementDecisions.CREATE_NEW_SPEC
                if create_new
                else SpecPlacementDecisions.EXTEND_EXISTING_SPEC,
                confidence=0.35,
                justification="Deterministic fallback used because no LLM decision was available.",
                evidence=["First E2E candidate selected from repository inventory"]
                if inventory.test_files
                else ["No E2E candidate specs found in repository inventory"],
                risk="medium",
                fallback="Create generated spec when placement confidence is insufficient",
            ),
        )
