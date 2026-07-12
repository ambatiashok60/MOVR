from worktop.ai_workspace.app.repository.infrastructure.git_cli_provider import GitCliProvider


class GitDiffService:
    def __init__(self, git_provider: GitCliProvider):
        self._git_provider = git_provider

    def diff_for_file(self, root: str, relative_path: str) -> str:
        return self._git_provider.diff(root, relative_path)

    def full_diff(self, root: str) -> str:
        return self._git_provider.diff(root)
