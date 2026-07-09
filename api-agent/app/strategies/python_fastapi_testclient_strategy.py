from __future__ import annotations

import re

from app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from app.schemas.execution_target import ExecutionTarget
from app.schemas.llm_outputs import GeneratedTestFileOutput
from app.schemas.repo_profile import RepoProfile
from app.strategies.base_strategy import ApiTestGenerationStrategy, StrategyMatch


class PythonFastApiTestClientStrategy(ApiTestGenerationStrategy):
    strategy_name = "python_fastapi_testclient"
    target_language = "python"
    test_framework = "pytest_fastapi_testclient"

    def supports(self, profile: RepoProfile) -> bool:
        return (
            profile.team_strategy.primary_language == "python"
            and "fastapi" in profile.team_strategy.service_frameworks
            and (
                "framework_testclient" in profile.team_strategy.test_frameworks
                or "framework TestClient fixture" in profile.team_strategy.client_patterns
            )
        )

    def match(self, profile: RepoProfile) -> StrategyMatch:
        reasons = ["Python FastAPI repository detected."]
        warnings: list[str] = []
        confidence = "medium"
        if "framework_testclient" in profile.team_strategy.test_frameworks:
            reasons.append("Existing framework TestClient tests detected.")
            confidence = "high"
        else:
            warnings.append("FastAPI TestClient strategy selected from weak repository signals.")
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
                    summary=f"pytest TestClient {target} API test skeleton for {request.scenario_name}",
                )
            )
        return files

    def prompt_guidance(self, profile: RepoProfile) -> str:
        return (
            "Generate pytest tests using the repository's FastAPI/framework TestClient "
            "fixture. Reuse conftest fixtures, auth header helpers, dependency overrides, "
            "and response assertion style from examples."
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
        method = (request.method or "post").lower()
        endpoint = request.endpoint or "/api/resource"
        client_arg = "stage_client" if target == ExecutionTarget.STAGE else "client"
        helpers = self._python_comment_lines("Detected helpers to reuse", self._helpers(profile))
        mocks = self._python_comment_lines("Mock/stub guidance", self._mock_guidance(profile))
        return f'''def test_{self._method_name(request.scenario_name)}({client_arg}):
    """TODO: Replace with this repo's fixtures, auth helpers, dependency overrides, and assertions."""
{helpers}
{mocks}
    # TODO: Build request payload with existing factories/fixtures when required.
    response = {client_arg}.{method}("{endpoint}")

    assert response.status_code < 500
'''

    def _helpers(self, profile: RepoProfile) -> list[str]:
        return [
            *profile.team_strategy.fixture_files[:3],
            *profile.team_strategy.auth_helpers[:3],
            *profile.team_strategy.api_client_helpers[:3],
            *profile.team_strategy.test_data_builders[:3],
        ]

    def _mock_guidance(self, profile: RepoProfile) -> list[str]:
        guidance: list[str] = []
        if "respx" in profile.team_strategy.mocking_frameworks:
            guidance.append("Use existing respx fixtures for outbound httpx calls.")
        if "responses" in profile.team_strategy.mocking_frameworks:
            guidance.append("Use existing responses fixtures for outbound requests calls.")
        if "pytest-mock" in profile.team_strategy.mocking_frameworks:
            guidance.append("Use existing mocker fixture patterns for service overrides.")
        if not guidance:
            guidance.append("Use FastAPI dependency overrides only when route dependencies require it.")
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
