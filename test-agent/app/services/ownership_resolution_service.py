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

from app.agents.ownership_resolution_agent import OwnershipResolutionAgent
from app.llm.llm_client import LLMClient
from app.schemas.ownership_resolution import OwnershipResolution
from app.schemas.repository_inventory import RepositoryInventory


class OwnershipResolutionService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.agent = OwnershipResolutionAgent(llm_client=llm_client)

    @log_performance("ownership_resolution_service.resolve")
    def resolve(self, inventory: RepositoryInventory) -> OwnershipResolution:
        log_step("ownership_resolution_service_started", {})
        try:
            return self.agent.resolve(inventory)
        except Exception as exc:
            log_exception(exc, context={"stage": "ownership_resolution"})
            raise
