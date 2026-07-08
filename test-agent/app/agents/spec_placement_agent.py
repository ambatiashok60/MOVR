from __future__ import annotations

from app.agents.base_agent import BaseAgent, log_exception, log_performance, logger
from app.prompts.spec_placement_prompt import build_spec_placement_prompt
from app.schemas.decision_trace import DecisionTrace
from app.schemas.functional_intent import FunctionalIntent
from app.schemas.repository_inventory import RepositoryInventory
from app.schemas.spec_placement import SpecPlacementDecision


class SpecPlacementAgent(BaseAgent):
    agent_name = "spec_placement_agent"

    @log_performance("spec_placement_agent.decide")
    def decide(
        self,
        inventory: RepositoryInventory,
        intent: FunctionalIntent | None = None,
    ) -> SpecPlacementDecision:
        context = self.log_start("spec_placement")
        try:
            decision = self.complete_structured(
                prompt=build_spec_placement_prompt(inventory=inventory, intent=intent),
                response_model=SpecPlacementDecision,
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
            log_exception(exc, context=context)
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
                decision="create_new_spec" if create_new else "extend_existing_spec",
                confidence=0.35,
                justification="Deterministic fallback used because no LLM decision was available.",
                evidence=["First E2E candidate selected from repository inventory"]
                if inventory.test_files
                else ["No E2E candidate specs found in repository inventory"],
                risk="medium",
                fallback="Create generated spec when placement confidence is insufficient",
            ),
        )
