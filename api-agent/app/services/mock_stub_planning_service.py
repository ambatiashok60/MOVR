from __future__ import annotations

from app.schemas.mock_stub_plan import MockStubPlan
from app.schemas.repo_profile import RepoProfile
from app.schemas.source_context import GenerationSourceContext
from app.tools.dependency_scanner_tool import DependencyScannerTool
from app.tools.mock_stub_scanner_tool import MockStubScannerTool


class MockStubPlanningService:
    def __init__(self) -> None:
        self.dependency_scanner = DependencyScannerTool()
        self.mock_scanner = MockStubScannerTool()

    def plan(
        self,
        profile: RepoProfile,
        source_context: GenerationSourceContext,
    ) -> MockStubPlan:
        dependencies = self.dependency_scanner.scan(source_context.endpoint_sources)
        strategy = self.mock_scanner.detect_strategy(profile)
        reused_helpers = self._reused_helpers(profile)
        generated_stubs = self._generated_stubs(strategy, dependencies)
        external_services = [
            dep.name
            for dep in dependencies
            if dep.dependency_kind in {"downstream_client", "http_client"}
        ]
        warnings: list[str] = []
        if dependencies and not strategy:
            warnings.append("Dependencies were detected but no mock/stub strategy was confidently found.")
        if not dependencies:
            warnings.append("No controller/route dependencies were detected for mock planning.")
        return MockStubPlan(
            strategy=strategy,
            reused_helpers=reused_helpers,
            dependencies_to_mock=dependencies,
            generated_stubs=generated_stubs,
            external_services_to_stub=external_services,
            warnings=warnings,
        )

    def _reused_helpers(self, profile: RepoProfile) -> list[str]:
        helpers = [
            *profile.team_strategy.auth_helpers[:5],
            *profile.team_strategy.fixture_files[:5],
            *profile.team_strategy.test_data_builders[:5],
            *profile.team_strategy.api_client_helpers[:5],
        ]
        return list(dict.fromkeys(helpers))[:12]

    def _generated_stubs(self, strategy: str | None, dependencies) -> list[str]:
        stubs: list[str] = []
        for dep in dependencies:
            if strategy == "mockito":
                target = dep.name or "dependency"
                stubs.append(f"when({target}....).thenReturn(...);")
            elif strategy in {"wiremock", "respx", "responses"}:
                stubs.append(f"Stub downstream call for {dep.name}.")
            elif strategy in {"pytest-mock", "pytest monkeypatch"}:
                stubs.append(f"Patch or fixture override for {dep.name}.")
        return stubs[:20]
