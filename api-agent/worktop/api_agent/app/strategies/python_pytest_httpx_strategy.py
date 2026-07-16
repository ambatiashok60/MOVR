from __future__ import annotations

import re

from worktop.api_agent.app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from worktop.api_agent.app.schemas.execution_target import ExecutionTarget
from worktop.api_agent.app.schemas.llm_outputs import GeneratedTestFileOutput
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.strategies.base_strategy import ApiTestGenerationStrategy, StrategyMatch


class PythonPytestHttpxStrategy(ApiTestGenerationStrategy):
    strategy_name = "python_pytest_httpx"
    target_language = "python"
    test_framework = "pytest_httpx"

    def supports(self, profile: RepoProfile) -> bool:
        return (
            profile.team_strategy.primary_language == "python"
            and (
                "httpx" in profile.team_strategy.test_frameworks
                or "requests" in profile.team_strategy.test_frameworks
                or "pytest" in profile.team_strategy.test_frameworks
            )
        )

    def match(self, profile: RepoProfile) -> StrategyMatch:
        reasons = ["Python pytest repository detected."]
        warnings: list[str] = []
        confidence = "medium"
        if "httpx" in profile.team_strategy.test_frameworks:
            reasons.append("Existing httpx usage detected.")
            confidence = "high"
        elif "requests" in profile.team_strategy.test_frameworks:
            reasons.append("Existing requests usage detected.")
            confidence = "medium"
        else:
            warnings.append("Generic pytest HTTP strategy selected without strong client evidence.")
        return StrategyMatch(self, confidence, reasons, warnings)

    def fallback_files(
        self,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
    ) -> list[GeneratedTestFileOutput]:
        files: list[GeneratedTestFileOutput] = []
        for target in self._targets(request):
            base_dir = self._base_dir(profile, target)
            filename = self._filename(request.scenario_name, target)
            files.append(
                GeneratedTestFileOutput(
                    relative_path=f"{base_dir}/{filename}",
                    content=self._content(request, profile, target),
                    test_target=str(target),
                    summary=f"pytest HTTP {target} API test skeleton for {request.scenario_name}",
                )
            )
        return files

    def prompt_guidance(self, profile: RepoProfile) -> str:
        return (
            "Generate pytest API tests using the repository's existing requests/httpx "
            "client fixtures, auth helpers, mocks, and response assertion conventions."
        )

    def _base_dir(self, profile: RepoProfile, target: ExecutionTarget) -> str:
        locations = (
            profile.team_strategy.stage_test_locations
            if target == ExecutionTarget.STAGE
            else profile.team_strategy.api_test_locations
        )
        return locations[0] if locations else "tests/api"

    def _filename(self, scenario_name: str, target: ExecutionTarget) -> str:
        words = re.findall(r"[A-Za-z0-9]+", scenario_name.lower())
        suffix = "_stage" if target == ExecutionTarget.STAGE else ""
        return f"test_{'_'.join(words[:7]) or 'generated_api'}{suffix}.py"

    def _content(
        self,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
        target: ExecutionTarget,
    ) -> str:
        method = (request.method or "GET").upper()
        endpoint = request.endpoint or "/api/resource"
        client_arg = "stage_api_client" if target == ExecutionTarget.STAGE else "api_client"
        helpers = self._python_comment_lines("Detected helpers to reuse", self._helpers(profile))
        mocks = self._python_comment_lines("Mock/stub guidance", self._mock_guidance(profile))
        return f'''def test_{self._method_name(request.scenario_name)}({client_arg}):
    """TODO: Replace with this repo's fixtures, auth helpers, and assertions."""
{helpers}
{mocks}
    response = {client_arg}.request("{method}", "{endpoint}")

    assert response.status_code < 500
'''

    def _helpers(self, profile: RepoProfile) -> list[str]:
        return [
            *profile.team_strategy.fixture_files[:3],
            *profile.team_strategy.auth_helpers[:3],
            *profile.team_strategy.api_client_helpers[:3],
            *profile.team_strategy.existing_ci_test_examples[:3],
        ]

    def _mock_guidance(self, profile: RepoProfile) -> list[str]:
        guidance: list[str] = []
        if "respx" in profile.team_strategy.mocking_frameworks:
            guidance.append("Use respx for outbound httpx dependency stubs.")
        if "responses" in profile.team_strategy.mocking_frameworks:
            guidance.append("Use responses for outbound requests dependency stubs.")
        if "pytest-mock" in profile.team_strategy.mocking_frameworks:
            guidance.append("Use mocker fixture patterns from existing tests.")
        if not guidance:
            guidance.append("Stub outbound clients only when source context shows external calls.")
        return guidance

    def _python_comment_lines(self, title: str, values: list[str]) -> str:
        if not values:
            return f"    # {title}: none detected."
        lines = [f"    # {title}:"]
        lines.extend(f"    # - {value}" for value in values[:8])
        return "\n".join(lines)

    def _method_name(self, scenario_name: str) -> str:
        words = re.findall(r"[A-Za-z0-9]+", scenario_name.lower())
        return "_".join(words[:8]) or "generated_api_scenario"
