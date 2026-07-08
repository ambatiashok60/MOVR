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

from app.inventory.inventory_builder import InventoryBuilder
from app.schemas.repository_inventory import RepositoryInventory
from app.schemas.test_file_classification import TestFileClassification


class InventoryService:
    def __init__(self) -> None:
        self.builder = InventoryBuilder()

    @log_performance("inventory_service.build")
    def build(
        self,
        repo_path: str,
        classifications: list[TestFileClassification],
    ) -> RepositoryInventory:
        log_step("inventory_build_started", {"repo_path": repo_path})
        try:
            inventory = self.builder.build(repo_path, classifications)
            log_metric("inventory_test_files_count", len(inventory.test_files))
            logger.info("Repository inventory built")
            return inventory
        except Exception as exc:
            log_exception(exc, context={"repo_path": repo_path, "stage": "inventory"})
            raise
