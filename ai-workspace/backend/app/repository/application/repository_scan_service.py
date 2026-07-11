from app.repository.domain.repository_tree import RepositoryTreeNode
from app.repository.infrastructure.local_repository_access_provider import LocalRepositoryAccessProvider


class RepositoryScanService:
    """Scans a workspace path into a tree, used both by workspace_path_service.py (to confirm
    a path 'has source files' during validation) and repository_tree_service.py (to serve the
    frontend's Repository Explorer)."""

    def __init__(self, provider: LocalRepositoryAccessProvider):
        self._provider = provider

    def scan(self, root: str) -> list[RepositoryTreeNode]:
        return self._provider.build_tree(root)

    def has_source_files(self, root: str) -> bool:
        return len(self.scan(root)) > 0
