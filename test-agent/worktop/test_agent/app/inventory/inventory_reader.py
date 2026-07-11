from __future__ import annotations

from worktop.test_agent.app.schemas.repository_inventory import RepositoryInventory


class InventoryReader:
    def e2e_specs(self, inventory: RepositoryInventory) -> list[str]:
        return [test.path for test in inventory.test_files if test.is_e2e_candidate]
