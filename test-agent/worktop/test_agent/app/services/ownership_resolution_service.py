from __future__ import annotations



from worktop.test_agent.app.agents.ownership_resolution_agent import OwnershipResolutionAgent
from worktop.test_agent.app.llm.llm_client import LLMClient
from worktop.test_agent.app.schemas.functional_intent import FunctionalIntent
from worktop.test_agent.app.schemas.ownership_resolution import OwnershipResolution
from worktop.test_agent.app.schemas.repository_inventory import RepositoryInventory
from worktop.test_agent.app.schemas.source_intelligence import SourceIntelligence
from worktop.core_services.app.utility.custom_logger.logging import logger



class OwnershipResolutionService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.agent = OwnershipResolutionAgent(llm_client=llm_client)

    def resolve(
        self,
        inventory: RepositoryInventory,
        source: SourceIntelligence | None = None,
        intent: FunctionalIntent | None = None,
    ) -> OwnershipResolution:
        logger.info("[playwright-generation] stage=ownership_resolution status=started")
        try:
            resolution = self.agent.resolve(inventory, source, intent)
            logger.info(
                "[playwright-generation] stage=ownership_resolution status=completed owner=%s kind=%s",
                resolution.owner_path,
                resolution.owner_kind,
            )
            return resolution
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=ownership_resolution status=failed_using_fallback error=%s",
                exc,
            )
            resolution = self.agent._fallback_resolution(inventory)
            logger.info(
                "[playwright-generation] stage=ownership_resolution status=fallback_completed owner=%s kind=%s",
                resolution.owner_path,
                resolution.owner_kind,
            )
            return resolution
