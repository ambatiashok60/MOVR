from __future__ import annotations

import logging


from app.inventory.inventory_builder import InventoryBuilder
from app.schemas.repository_inventory import RepositoryInventory
from app.schemas.test_file_classification import TestFileClassification

logger = logging.getLogger(__name__)


class InventoryService:
    def __init__(self) -> None:
        self.builder = InventoryBuilder()

    def build(
        self,
        repo_path: str,
        classifications: list[TestFileClassification],
    ) -> RepositoryInventory:
        logger.info("[playwright-generation] stage=inventory status=started repo=%s", repo_path)
        try:
            inventory = self.builder.build(repo_path, classifications)
            logger.info(
                "[playwright-generation] stage=inventory status=completed test_files=%s",
                len(inventory.test_files),
            )
            return inventory
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=inventory status=failed repo=%s error=%s",
                repo_path,
                exc,
            )
            raise
