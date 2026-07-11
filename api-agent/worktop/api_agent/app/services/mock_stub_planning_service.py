from __future__ import annotations

from worktop.api_agent.app.schemas.mock_stub_plan import MockStubPlan
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.source_context import GenerationSourceContext
from worktop.api_agent.app.tools.dependency_scanner_tool import DependencyScannerTool
from worktop.api_agent.app.tools.mock_stub_scanner_tool import MockStubScannerTool
from worktop.api_agent.app.utils.logging_utils import log_step


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
        runtime_signals = [
            f"{dep.dependency_kind}:{dep.name}"
            for dep in dependencies
            if dep.dependency_kind in {
                "message_broker", "cloud_service", "secret_store",
                "dynamic_configuration", "dynamic_runtime",
            }
        ]
        high_risk = [
            dep for dep in dependencies
            if dep.dependency_kind in {"message_broker", "cloud_service", "secret_store"}
        ]
        approval_reasons = [
            f"{dep.dependency_kind} `{dep.name}` may require external infrastructure or credentials."
            for dep in high_risk
        ]
        provisioning_actions = [
            f"Create an isolated test double/container for {dep.name}; never connect to production."
            for dep in high_risk
        ]
        auth_helpers = profile.team_strategy.auth_helpers
        auth_strategy = (
            f"Reuse repository auth helper `{auth_helpers[0]}`"
            if auth_helpers else
            "Generate an isolated fake identity/token provider; do not embed credentials."
        )
        if not auth_helpers:
            warnings.append("No repository-native authentication helper was detected.")
        plan = MockStubPlan(
            strategy=strategy,
            reused_helpers=reused_helpers,
            dependencies_to_mock=dependencies,
            generated_stubs=generated_stubs,
            external_services_to_stub=external_services,
            warnings=warnings,
            risk_level="high" if high_risk else ("medium" if dependencies else "low"),
            approval_required=bool(high_risk),
            approval_reasons=approval_reasons,
            runtime_signals=runtime_signals,
            provisioning_actions=provisioning_actions,
            auth_strategy=auth_strategy,
        )
        log_step(
            "api_mock_stub_plan_completed",
            {
                "strategy": plan.strategy,
                "dependency_count": len(plan.dependencies_to_mock),
                "reused_helper_count": len(plan.reused_helpers),
                "generated_stub_count": len(plan.generated_stubs),
                "risk_level": plan.risk_level,
                "approval_required": plan.approval_required,
                "runtime_signal_count": len(plan.runtime_signals),
            },
        )
        return plan

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
