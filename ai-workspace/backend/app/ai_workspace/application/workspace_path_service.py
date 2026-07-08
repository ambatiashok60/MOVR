import uuid

from app.ai_workspace.infrastructure.local_workspace_provider import LocalWorkspaceProvider
from app.repository.application.repository_scan_service import RepositoryScanService


class WorkspaceValidationResult:
    def __init__(self, path: str, is_valid: bool, message: str | None, repository_id: str | None, has_git: bool):
        self.path = path
        self.is_valid = is_valid
        self.message = message
        self.repository_id = repository_id
        self.has_git = has_git


class WorkspacePathService:
    """Validates a local repo path before anything else in AI Workspace touches it. This is
    the one gate — repository_scan_service.py and every tool that reads/writes by path still
    apply their own root-escape checks (common/path_safety.py), but this is what decides
    whether a path is usable as a workspace root at all."""

    def __init__(self, provider: LocalWorkspaceProvider, scan_service: RepositoryScanService):
        self._provider = provider
        self._scan_service = scan_service

    def validate(self, path: str) -> WorkspaceValidationResult:
        if not self._provider.exists_and_is_directory(path):
            return WorkspaceValidationResult(path, False, "Path does not exist or is not a directory", None, False)

        if not self._scan_service.has_source_files(path):
            return WorkspaceValidationResult(path, False, "No source files found in this path", None, False)

        has_git = self._provider.has_git(path)
        repository_id = str(uuid.uuid5(uuid.NAMESPACE_URL, path))
        return WorkspaceValidationResult(path, True, None, repository_id, has_git)
