from worktop.ai_workspace.app.repository.domain.repository_tree import RepositoryTreeNode
from worktop.ai_workspace.app.repository.application.repository_scan_service import RepositoryScanService


class RepositoryTreeService:
    """Read path for the frontend's file tree. Deliberately not cached in V1 — every call
    re-scans the filesystem, which is fine at workspace scale but would need caching if
    workspaces grow large enough for scan time to matter."""

    def __init__(self, scan_service: RepositoryScanService):
        self._scan_service = scan_service

    def get_tree(self, root: str) -> list[RepositoryTreeNode]:
        return self._scan_service.scan(root)
