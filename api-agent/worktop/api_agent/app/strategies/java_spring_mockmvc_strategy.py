from __future__ import annotations

import re

from worktop.api_agent.app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from worktop.api_agent.app.schemas.execution_target import ExecutionTarget
from worktop.api_agent.app.schemas.llm_outputs import GeneratedTestFileOutput
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.strategies.base_strategy import ApiTestGenerationStrategy, StrategyMatch


class JavaSpringMockMvcStrategy(ApiTestGenerationStrategy):
    strategy_name = "java_spring_mockmvc"
    target_language = "java"
    test_framework = "junit5_mockmvc"

    def supports(self, profile: RepoProfile) -> bool:
        return (
            profile.team_strategy.primary_language == "java"
            and "spring_boot" in profile.team_strategy.service_frameworks
            and (
                "mockmvc" in profile.team_strategy.test_frameworks
                or "MockMvc for controller/API-slice CI tests" in profile.team_strategy.client_patterns
            )
        )

    def match(self, profile: RepoProfile) -> StrategyMatch:
        reasons = ["Java Spring Boot repository detected."]
        warnings: list[str] = []
        confidence = "medium"
        if "mockmvc" in profile.team_strategy.test_frameworks:
            reasons.append("Existing MockMvc tests detected.")
            confidence = "high"
        else:
            warnings.append("MockMvc was inferred from Spring context but not strongly detected.")
        return StrategyMatch(self, confidence, reasons, warnings)

    def fallback_files(
        self,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
    ) -> list[GeneratedTestFileOutput]:
        files: list[GeneratedTestFileOutput] = []
        for target in self._targets(request):
            base_dir = self._base_dir(profile, target)
            class_name = self._class_name(request.scenario_name, target)
            files.append(
                GeneratedTestFileOutput(
                    relative_path=f"{base_dir}/{class_name}.java",
                    content=self._content(class_name, request, profile, target),
                    test_target=str(target),
                    summary=f"Spring MockMvc {target} API test skeleton for {request.scenario_name}",
                )
            )
        return files

    def prompt_guidance(self, profile: RepoProfile) -> str:
        return (
            "Generate Spring Boot JUnit 5 tests using MockMvc for CI-safe API-slice "
            "coverage. Reuse existing @WebMvcTest/@SpringBootTest setup, auth helpers, "
            "fixtures, ObjectMapper conventions, and Mockito mocks from examples."
        )

    def _base_dir(self, profile: RepoProfile, target: ExecutionTarget) -> str:
        locations = (
            profile.team_strategy.stage_test_locations
            if target == ExecutionTarget.STAGE
            else profile.team_strategy.api_test_locations
        )
        return locations[0] if locations else "src/test/java/generated/api"

    def _class_name(self, scenario_name: str, target: ExecutionTarget) -> str:
        words = re.findall(r"[A-Za-z0-9]+", scenario_name)
        suffix = "IT" if target == ExecutionTarget.STAGE else "ControllerTest"
        return "".join(word[:1].upper() + word[1:] for word in words[:6]) + suffix

    def _method_name(self, scenario_name: str) -> str:
        words = re.findall(r"[A-Za-z0-9]+", scenario_name)
        if not words:
            return "generatedApiScenario"
        first, *rest = words[:8]
        return first[:1].lower() + first[1:] + "".join(word[:1].upper() + word[1:] for word in rest)

    def _content(
        self,
        class_name: str,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
        target: ExecutionTarget,
    ) -> str:
        method = request.method or "POST"
        endpoint = request.endpoint or "/api/resource"
        helpers = self._comment_lines("Detected helpers to reuse", self._helpers(profile))
        mocks = self._comment_lines("Mock/stub guidance", self._mock_guidance(profile))
        target_guidance = (
            "Stage target selected: prefer repo's stage/integration setup if MockMvc is not used there."
            if target == ExecutionTarget.STAGE
            else "CI target selected: keep this API-slice test local and deterministic."
        )
        return f"""package generated.api;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class {class_name} {{

    @Test
    void {self._method_name(request.scenario_name)}() {{
        // {target_guidance}
{helpers}
{mocks}
        // TODO: Wire this to the repo's MockMvc field/fixture and perform the request below.
        String method = "{method}";
        String endpoint = "{endpoint}";

        assertThat(method).isNotBlank();
        assertThat(endpoint).startsWith("/");
    }}
}}
"""

    def _helpers(self, profile: RepoProfile) -> list[str]:
        return [
            *profile.team_strategy.auth_helpers[:3],
            *profile.team_strategy.fixture_files[:3],
            *profile.team_strategy.test_data_builders[:3],
            *profile.team_strategy.api_client_helpers[:3],
        ]

    def _mock_guidance(self, profile: RepoProfile) -> list[str]:
        guidance: list[str] = []
        if "mockito" in profile.team_strategy.mocking_frameworks:
            guidance.append("Use existing Mockito/@MockBean service stubs from nearby controller tests.")
        if "wiremock" in profile.team_strategy.mocking_frameworks:
            guidance.append("Use existing WireMock setup for downstream HTTP clients.")
        if not guidance:
            guidance.append("Detect controller dependencies and add @MockBean stubs only when required.")
        return guidance

    def _comment_lines(self, title: str, values: list[str]) -> str:
        if not values:
            return f"        // {title}: none detected."
        lines = [f"        // {title}:"]
        lines.extend(f"        // - {value}" for value in values[:8])
        return "\n".join(lines)
