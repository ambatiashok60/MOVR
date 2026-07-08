import os
from pathlib import Path

from app.common.path_safety import resolve_within_root
from app.repository.domain.file_metadata import FileMetadata
from app.repository.domain.repository_file import RepositoryFile
from app.repository.domain.repository_tree import RepositoryTreeNode

IGNORED_DIR_NAMES = {"node_modules", ".git", "dist", "build", "coverage", "__pycache__", ".venv"}

_BINARY_PROBE_BYTES = 8192


def _is_probably_binary(sample: bytes) -> bool:
    return b"\x00" in sample


class LocalRepositoryAccessProvider:
    """Filesystem-backed implementation of repository access. The only place in the codebase
    that touches `os`/`pathlib` directly for reading workspace files — repository_scan_service.py,
    repository_tree_service.py, and file_read_service.py all go through this."""

    def build_tree(self, root: str) -> list[RepositoryTreeNode]:
        root_path = Path(root).resolve()
        return self._build_tree_level(root_path, root_path)

    def _build_tree_level(self, root_path: Path, current: Path) -> list[RepositoryTreeNode]:
        nodes: list[RepositoryTreeNode] = []
        try:
            entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except (FileNotFoundError, NotADirectoryError, PermissionError):
            return nodes

        for entry in entries:
            if entry.name in IGNORED_DIR_NAMES:
                continue
            relative_path = str(entry.relative_to(root_path))
            if entry.is_dir():
                nodes.append(
                    RepositoryTreeNode(
                        id=relative_path,
                        name=entry.name,
                        path=relative_path,
                        type="folder",
                        children=self._build_tree_level(root_path, entry),
                    )
                )
            else:
                nodes.append(
                    RepositoryTreeNode(id=relative_path, name=entry.name, path=relative_path, type="file")
                )
        return nodes

    def read_file(self, root: str, relative_path: str) -> RepositoryFile:
        target = resolve_within_root(root, relative_path)
        raw = target.read_bytes()
        is_binary = _is_probably_binary(raw[:_BINARY_PROBE_BYTES])
        content = "" if is_binary else raw.decode("utf-8", errors="replace")

        metadata = FileMetadata(
            path=relative_path,
            size_bytes=len(raw),
            is_binary=is_binary,
            language=target.suffix.lstrip(".") or None,
        )
        return RepositoryFile(metadata=metadata, content=content)

    def search(self, root: str, query: str, max_results: int = 50) -> list[str]:
        root_path = Path(root).resolve()
        matches: list[str] = []
        query_lower = query.lower()

        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIR_NAMES]
            for filename in filenames:
                if query_lower in filename.lower():
                    full_path = Path(dirpath) / filename
                    matches.append(str(full_path.relative_to(root_path)))
                    if len(matches) >= max_results:
                        return matches
        return matches
