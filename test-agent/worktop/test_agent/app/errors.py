from __future__ import annotations

from worktop.test_agent.app.schemas.repo_profile import RepoProfile


class UnsupportedRepositoryError(RuntimeError):
    def __init__(self, profile: RepoProfile) -> None:
        self.profile = profile
        blockers = "; ".join(profile.support_blockers) or "Repository is outside beta scope"
        super().__init__(f"Unsupported repository for Playwright beta generation: {blockers}")
