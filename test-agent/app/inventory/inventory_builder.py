from __future__ import annotations

from pathlib import Path

from app.inventory.file_fingerprint import fingerprint_file
from app.schemas.repository_inventory import RepositoryInventory
from app.schemas.test_file_classification import TestFileClassification
from app.tools.git_tool import GitTool


class InventoryBuilder:
    def __init__(self) -> None:
        self.git = GitTool()

    def build(
        self,
        repo_path: str,
        classifications: list[TestFileClassification],
    ) -> RepositoryInventory:
        root = Path(repo_path)
        file_hashes = {
            str(path.relative_to(root)): fingerprint_file(path)
            for path in root.rglob("*")
            if path.is_file() and ".git" not in path.parts
        }
        return RepositoryInventory(
            repo_path=repo_path,
            repo_head=self.git.head(repo_path),
            file_hashes=file_hashes,
            test_files=classifications,
        )
