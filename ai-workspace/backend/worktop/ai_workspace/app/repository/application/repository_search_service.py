from worktop.ai_workspace.app.repository.infrastructure.local_repository_access_provider import LocalRepositoryAccessProvider


class RepositorySearchService:
    """Filename/path search only for V1 — content search (grep-style) is a reasonable next
    tool but isn't wired in yet; search_repository_tool.py calls this and would need a second
    method here to support content search."""

    def __init__(self, provider: LocalRepositoryAccessProvider):
        self._provider = provider

    def search_by_name(self, root: str, query: str) -> list[str]:
        return self._provider.search(root, query)
