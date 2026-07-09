from __future__ import annotations

import re

from app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from app.schemas.execution_target import ExecutionTarget
from app.schemas.llm_outputs import GeneratedTestFileOutput
from app.schemas.repo_profile import RepoProfile
from app.strategies.base_strategy import ApiTestGenerationStrategy, StrategyMatch


class JavaSpringRestAssuredStrategy(ApiTestGenerationStrategy):
    strategy_name = "java_spring_rest_assured"
    target_language = "java"
    test_framework = "junit5_rest_assured"

    def supports(self, profile: RepoProfile) -> bool:
        return (
            profile.team_strategy.primary_language == "java"
            and (
                "rest_assured" in profile.team_strategy.test_frameworks
                or "RestAssured for integration or stage tests" in profile.team_strategy.client_patterns
            )
        )

    def match(self, profile: RepoProfile) -> StrategyMatch:
        reasons = ["Java repository detected."]
        warnings: list[str] = []
        confidence = "medium"
        if "rest_assured" in profile.team_strategy.test_frameworks:
            reasons.append("Existing RestAssured tests detected.")
            confidence = "high"
        else:
            warnings.append("RestAssured strategy selected from weak repository signals.")
        return StrategyMatch(self, confidence, reasons, warnings)

    def fallback_files(
        self,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
    ) -> list[GeneratedTestFileOutput]:
        files: list[GeneratedTestFileOutput] = []
        for target in self._targets(request):
            class_name = self._class_name(request.scenario_name, target)
            base_dir = self._base_dir(profile, target)
            files.append(
                GeneratedTestFileOutput(
                    relative_path=f"{base_dir}/{class_name}.java",
                    content=self._content(class_name, request, profile, target),
                    test_target=str(target),
                    summary=f"RestAssured {target} API test skeleton for {request.scenario_name}",
                )
            )
        return files

    def prompt_guidance(self, profile: RepoProfile) -> str:
        return (
            "Generate JUnit 5 RestAssured API tests. Reuse existing base URI setup, "
            "request specs, auth token helpers, fixtures, and environment conventions."
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
        suffix = "StageIT" if target == ExecutionTarget.STAGE else "ApiIT"
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
        target_guidance = (
            "Stage target selected: use deployed base URL/environment config and safe test data cleanup."
            if target == ExecutionTarget.STAGE
            else "CI target selected: use local app/random port or mocked downstreams if this repo supports it."
        )
        return f"""package generated.api;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class {class_name} {{

    @Test
    void {self._method_name(request.scenario_name)}() {{
        // {target_guidance}
{helpers}
        // TODO: Replace with this repo's RestAssured request spec, auth helpers, and assertions.
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
            *profile.team_strategy.api_client_helpers[:3],
            *profile.team_strategy.existing_stage_test_examples[:3],
        ]

    def _comment_lines(self, title: str, values: list[str]) -> str:
        if not values:
            return f"        // {title}: none detected."
        lines = [f"        // {title}:"]
        lines.extend(f"        // - {value}" for value in values[:8])
        return "\n".join(lines)
