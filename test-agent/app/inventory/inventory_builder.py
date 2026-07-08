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
            if path.is_file() and not self._is_ignored_path(path)
        }
        paths = [Path(path) for path in file_hashes]
        return RepositoryInventory(
            repo_path=repo_path,
            repo_head=self.git.head(repo_path),
            file_hashes=file_hashes,
            test_files=classifications,
            page_objects=self._matching_paths(paths, ("page", "pages", "po", "page-object", "page_objects")),
            fixtures=self._matching_paths(paths, ("fixture", "fixtures")),
            helpers=self._matching_paths(paths, ("helper", "helpers", "support", "utils", "mock", "mocks", "stub", "stubs")),
        )

    def _matching_paths(self, paths: list[Path], signals: tuple[str, ...]) -> list[str]:
        matches: list[str] = []
        for path in paths:
            parts = {part.lower() for part in path.parts}
            stem = path.stem.lower()
            if parts.intersection(signals) or any(signal in stem for signal in signals):
                if path.suffix in {".ts", ".tsx", ".js", ".jsx", ".json"}:
                    matches.append(str(path))
        return sorted(set(matches))

    def _is_ignored_path(self, path: Path) -> bool:
        ignored_parts = {
            ".git",
            "node_modules",
            "dist",
            "build",
            "coverage",
            ".next",
            ".turbo",
            ".nx",
            "__pycache__",
            ".venv",
        }
        return bool(set(path.parts).intersection(ignored_parts))
