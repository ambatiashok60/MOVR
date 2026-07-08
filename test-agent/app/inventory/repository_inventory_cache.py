from __future__ import annotations

import json
from pathlib import Path

from app.schemas.repository_inventory import RepositoryInventory


class RepositoryInventoryCache:
    def cache_path(self, repo_path: str) -> Path:
        return Path(repo_path, ".playwright-agent-cache", "inventory.json")

    def load(self, repo_path: str) -> RepositoryInventory | None:
        path = self.cache_path(repo_path)
        if not path.exists():
            return None
        return RepositoryInventory.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, repo_path: str, inventory: RepositoryInventory) -> None:
        path = self.cache_path(repo_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(inventory.model_dump(), indent=2), encoding="utf-8")
