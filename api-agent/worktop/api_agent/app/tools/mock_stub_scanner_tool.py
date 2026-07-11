from __future__ import annotations

from worktop.api_agent.app.schemas.repo_profile import RepoProfile


class MockStubScannerTool:
    def detect_strategy(self, profile: RepoProfile) -> str | None:
        frameworks = set(profile.team_strategy.mocking_frameworks)
        tests = set(profile.team_strategy.test_frameworks)
        if "mockito" in frameworks or "mockmvc" in tests:
            return "mockito"
        if "wiremock" in frameworks:
            return "wiremock"
        if "respx" in frameworks:
            return "respx"
        if "responses" in frameworks:
            return "responses"
        if "pytest-mock" in frameworks:
            return "pytest-mock"
        if profile.team_strategy.primary_language == "python":
            return "pytest monkeypatch"
        if profile.team_strategy.primary_language == "java":
            return "mockito"
        return None
