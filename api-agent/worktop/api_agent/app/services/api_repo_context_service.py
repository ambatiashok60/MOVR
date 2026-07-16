from __future__ import annotations

from pathlib import Path

from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.services.team_test_strategy_service import TeamTestStrategyService
from worktop.api_agent.app.services.capability_assessment_service import CapabilityAssessmentService
from worktop.api_agent.app.autonomy.workflow_controller import AutonomousDiscoveryWorkflowController
from worktop.api_agent.app.autonomy.strategy_composer import CapabilityStrategyComposer
from worktop.api_agent.app.tools.api_endpoint_scanner_tool import ApiEndpointScannerTool
from worktop.api_agent.app.tools.existing_test_scanner_tool import ExistingTestScannerTool
from worktop.api_agent.app.tools.path_safety import resolve_workspace_path
from worktop.api_agent.app.utils.logging_utils import log_step
from worktop.api_agent.app.config import settings


class ApiRepoContextService:
    def __init__(self) -> None:
        self.endpoint_scanner = ApiEndpointScannerTool()
        self.test_scanner = ExistingTestScannerTool()
        self.strategy_service = TeamTestStrategyService()
        self.capability_assessment = CapabilityAssessmentService()
        self.autonomous_discovery = AutonomousDiscoveryWorkflowController(self.capability_assessment)
        self.strategy_composer = CapabilityStrategyComposer()

    def build(self, repo_path: str) -> RepoProfile:
        log_step("api_repo_context_started", {"repo_path": repo_path, "stage": "scanning_repository"})
        root = resolve_workspace_path(repo_path)
        profile = RepoProfile(
            repo_path=str(root),
            package_manager=self._package_manager(root),
            build_tool=self._build_tool(root),
            languages=self._languages(root),
            endpoints=self.endpoint_scanner.scan(str(root)),
            existing_tests=self.test_scanner.scan(str(root)),
        )
        profile.team_strategy = self.strategy_service.discover(str(root), profile)
        profile.service_frameworks = profile.team_strategy.service_frameworks
        profile.api_styles = profile.team_strategy.api_styles
        profile.test_frameworks = profile.team_strategy.test_frameworks
        profile.mocking_frameworks = profile.team_strategy.mocking_frameworks
        profile.contract_tools = profile.team_strategy.contract_tools
        profile.findings = self._findings(profile)
        profile.warnings = profile.team_strategy.warnings
        if settings.enable_capability_discovery:
            profile.capability_assessment = self.autonomous_discovery.run(profile)
            profile.generation_plan = self.strategy_composer.compose(profile)
        return profile

    def _package_manager(self, root: Path) -> str | None:
        if (root / "pnpm-lock.yaml").exists():
            return "pnpm"
        if (root / "yarn.lock").exists():
            return "yarn"
        if (root / "package-lock.json").exists():
            return "npm"
        return None

    def _build_tool(self, root: Path) -> str | None:
        if (root / "pom.xml").exists():
            return "maven"
        if (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
            return "gradle"
        if (root / "package.json").exists():
            return "node"
        if (root / "pyproject.toml").exists():
            return "python"
        return None

    def _languages(self, root: Path) -> list[str]:
        suffix_map = {
            ".java": "java",
            ".kt": "kotlin",
            ".ts": "typescript",
            ".js": "javascript",
            ".py": "python",
            ".go": "go",
            ".cs": "csharp",
        }
        found: set[str] = set()
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in suffix_map:
                found.add(suffix_map[path.suffix])
            if len(found) >= 4:
                break
        return sorted(found)

    def _findings(self, profile: RepoProfile) -> list[str]:
        findings = [
            f"Detected {len(profile.endpoints)} API endpoint candidates.",
            f"Detected {len(profile.existing_tests)} existing API test candidates.",
        ]
        if profile.build_tool:
            findings.append(f"Detected build tool: {profile.build_tool}.")
        if profile.package_manager:
            findings.append(f"Detected package manager: {profile.package_manager}.")
        if profile.team_strategy.primary_language:
            findings.append(f"Detected primary language: {profile.team_strategy.primary_language}.")
        if profile.team_strategy.service_frameworks:
            findings.append(
                "Detected service frameworks: "
                + ", ".join(profile.team_strategy.service_frameworks)
                + "."
            )
        if profile.team_strategy.test_frameworks:
            findings.append(
                "Detected test frameworks: "
                + ", ".join(profile.team_strategy.test_frameworks)
                + "."
            )
        findings.append(f"Team strategy confidence: {profile.team_strategy.confidence}.")
        return findings
