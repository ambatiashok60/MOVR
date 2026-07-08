from __future__ import annotations

from app.agents.base_agent import BaseAgent, log_exception, log_performance
from app.prompts.ownership_resolution_prompt import build_ownership_resolution_prompt
from app.schemas.ownership_resolution import OwnershipResolution
from app.schemas.repository_inventory import RepositoryInventory


class OwnershipResolutionAgent(BaseAgent):
    agent_name = "ownership_resolution_agent"

    @log_performance("ownership_resolution_agent.resolve")
    def resolve(self, inventory: RepositoryInventory) -> OwnershipResolution:
        context = self.log_start("ownership_resolution")
        try:
            return self.complete_structured(
                prompt=build_ownership_resolution_prompt(inventory),
                response_model=OwnershipResolution,
            )
        except Exception as exc:
            log_exception(exc, context=context)
            raise

    def _fallback_resolution(
        self,
        inventory: RepositoryInventory,
    ) -> OwnershipResolution:
        owner_path = inventory.page_objects[0] if inventory.page_objects else "spec"
        return OwnershipResolution(
            owner_path=owner_path,
            owner_kind="page_object" if inventory.page_objects else "spec",
            confidence=0.35,
            reason="Deterministic fallback used because no LLM decision was available.",
        )
