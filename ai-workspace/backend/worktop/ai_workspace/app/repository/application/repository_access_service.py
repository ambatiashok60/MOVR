from worktop.ai_workspace.app.repository.domain.repository_file import RepositoryFile
from worktop.ai_workspace.app.repository.infrastructure.local_repository_access_provider import LocalRepositoryAccessProvider


class RepositoryAccessService:
    """Facade the rest of the app depends on instead of LocalRepositoryAccessProvider directly
    — keeps the door open for a non-local provider (e.g. a remote repo API) later without
    touching callers."""

    def __init__(self, provider: LocalRepositoryAccessProvider):
        self._provider = provider

    def read_file(self, root: str, relative_path: str) -> RepositoryFile:
        return self._provider.read_file(root, relative_path)
