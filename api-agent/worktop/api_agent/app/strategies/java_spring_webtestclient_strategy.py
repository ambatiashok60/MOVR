from __future__ import annotations

import re

from worktop.api_agent.app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from worktop.api_agent.app.schemas.execution_target import ExecutionTarget
from worktop.api_agent.app.schemas.llm_outputs import GeneratedTestFileOutput
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.strategies.base_strategy import ApiTestGenerationStrategy, StrategyMatch


class JavaSpringWebTestClientStrategy(ApiTestGenerationStrategy):
    strategy_name = "java_spring_webtestclient"
    target_language = "java"
    test_framework = "junit5_webtestclient"

    def supports(self, profile: RepoProfile) -> bool:
        assessment = profile.capability_assessment
        names = {item.name for item in assessment.capabilities} if assessment else set()
        return profile.team_strategy.primary_language == "java" and ("spring_webflux" in names or "webtestclient" in names)

    def match(self, profile: RepoProfile) -> StrategyMatch:
        names = {item.name for item in profile.capability_assessment.capabilities} if profile.capability_assessment else set()
        established = "webtestclient" in names
        return StrategyMatch(self, "high" if established else "medium", ["Spring WebFlux/reactive source detected.", *(["Existing WebTestClient tests detected."] if established else [])], [] if established else ["WebTestClient convention is source-derived and requires review."])

    def fallback_files(self, request: GenerateApiTestCodeRequest, profile: RepoProfile) -> list[GeneratedTestFileOutput]:
        words = re.findall(r"[A-Za-z0-9]+", request.scenario_name)
        class_name = "".join(word[:1].upper() + word[1:] for word in words[:6]) + "WebFluxTest"
        method_name = (words[0][:1].lower() + words[0][1:] + "".join(word[:1].upper() + word[1:] for word in words[1:8])) if words else "generatedReactiveScenario"
        endpoint = request.endpoint or "/api/resource"
        content = f'''package generated.api;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.web.reactive.server.WebTestClient;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class {class_name} {{
    @Autowired WebTestClient webTestClient;

    @Test
    void {method_name}() {{
        webTestClient.get().uri("{endpoint}")
            .exchange()
            .expectStatus().is2xxSuccessful()
            .expectBody();
    }}
}}
'''
        return [GeneratedTestFileOutput(relative_path=f"src/test/java/generated/api/{class_name}.java", content=content, test_target=str(ExecutionTarget.CI), summary=f"WebTestClient reactive API scaffold for {request.scenario_name}")]

    def prompt_guidance(self, profile: RepoProfile) -> str:
        return "Generate JUnit 5 WebTestClient tests for Spring WebFlux. Reuse repository bootstrap/auth/fixtures. For outbound WebClient dependencies use the composed MockWebServer or WireMock substitution; never deep-stub the fluent WebClient chain. Avoid Thread.sleep and blocking reactive flows."
