from __future__ import annotations

from worktop.test_agent.app.agents.base_agent import BaseAgent, logger
from worktop.test_agent.app.prompts.ownership_resolution_prompt import build_ownership_resolution_prompt
from worktop.test_agent.app.schemas.decision_trace import DecisionTrace
from worktop.test_agent.app.schemas.functional_intent import FunctionalIntent
from worktop.test_agent.app.schemas.ownership_resolution import OwnershipResolution
from worktop.test_agent.app.schemas.repository_inventory import RepositoryInventory
from worktop.test_agent.app.schemas.source_intelligence import SourceIntelligence


class OwnershipResolutionAgent(BaseAgent):
    agent_name = "ownership_resolution_agent"

    def resolve(
        self,
        inventory: RepositoryInventory,
        source: SourceIntelligence | None = None,
        intent: FunctionalIntent | None = None,
    ) -> OwnershipResolution:
        context = self.log_start("ownership_resolution")
        try:
            return self.complete_structured(
                prompt=build_ownership_resolution_prompt(inventory, source, intent),
                response_model=OwnershipResolution,
            )
        except Exception as exc:
            logger.exception(
                "[playwright-generation] agent=%s stage=ownership_resolution status=failed context=%s error=%s",
                self.agent_name,
                context,
                exc,
            )
            raise

    def _fallback_resolution(
        self,
        inventory: RepositoryInventory,
    ) -> OwnershipResolution:
        has_page_objects = bool(inventory.page_objects)
        owner_path = inventory.page_objects[0] if has_page_objects else "spec"
        owner_kind = "page_object" if has_page_objects else "spec"
        return OwnershipResolution(
            owner_path=owner_path,
            owner_kind=owner_kind,
            create_new=False,
            confidence=0.35,
            reason="Deterministic fallback used because no LLM decision was available.",
            decision_trace=DecisionTrace(
                decision=f"reuse_existing_{owner_kind}",
                confidence=0.35,
                justification=(
                    "Deterministic fallback reuses an existing owner because no LLM "
                    "decision was available; inventing a new owner would be unsafe."
                ),
                evidence=[
                    "First existing page object selected from inventory"
                    if has_page_objects
                    else "No page object convention found; defaulting to the spec"
                ],
                risk="medium",
                fallback="Reuse an existing owner when ownership confidence is insufficient.",
            ),
        )
