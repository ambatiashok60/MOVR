from __future__ import annotations

import re

from worktop.api_agent.app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from worktop.api_agent.app.schemas.execution_target import ExecutionTarget
from worktop.api_agent.app.schemas.llm_outputs import GeneratedTestFileOutput
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.strategies.base_strategy import ApiTestGenerationStrategy, StrategyMatch


class JavaSpringGraphQlTesterStrategy(ApiTestGenerationStrategy):
    strategy_name = "java_spring_graphql_tester"
    target_language = "java"
    test_framework = "junit5_graphql_tester"

    def supports(self, profile: RepoProfile) -> bool:
        assessment = profile.capability_assessment
        names = {item.name for item in assessment.capabilities} if assessment else set()
        return "java" in profile.languages and bool({"graphql", "spring_graphql"} & names)

    def match(self, profile: RepoProfile) -> StrategyMatch:
        assessment = profile.capability_assessment
        names = {item.name for item in assessment.capabilities} if assessment else set()
        driver = next((name for name in ("http_graphql_tester", "web_graphql_tester", "execution_graphql_tester", "graphql_tester") if name in names), None)
        return StrategyMatch(self, "high" if driver else "medium", ["Spring GraphQL schema or resolver evidence detected.", *([f"Existing {driver} tests detected."] if driver else [])], [] if driver else ["GraphQlTester selection is source-derived and requires review."])

    def fallback_files(self, request: GenerateApiTestCodeRequest, profile: RepoProfile) -> list[GeneratedTestFileOutput]:
        operation_type, operation = self._operation(profile)
        words = re.findall(r"[A-Za-z0-9]+", request.scenario_name)
        class_name = "".join(word[:1].upper() + word[1:] for word in words[:6]) + "GraphQlTest"
        method_name = (words[0][:1].lower() + words[0][1:] + "".join(word[:1].upper() + word[1:] for word in words[1:8])) if words else "generatedGraphQlScenario"
        document = f"{operation_type} GeneratedScenario {{ {operation} }}"
        content = f'''package generated.api;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.graphql.test.tester.HttpGraphQlTester;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class {class_name} {{
    @Autowired HttpGraphQlTester graphQlTester;

    @Test
    void {method_name}() {{
        graphQlTester.document("""
            {document}
            """)
            .execute()
            .errors().verify()
            .path("{operation}").hasValue();
    }}
}}
'''
        return [GeneratedTestFileOutput(relative_path=f"src/test/java/generated/api/{class_name}.java", content=content, test_target=str(ExecutionTarget.CI), summary=f"Spring GraphQlTester scaffold for {request.scenario_name}")]

    def prompt_guidance(self, profile: RepoProfile) -> str:
        return "Generate Spring GraphQlTester/JUnit 5 tests. Use actual schema operation names, variables, selection sets, authentication, GraphQL error assertions, and repository fixtures. Reuse HttpGraphQlTester, WebGraphQlTester, or ExecutionGraphQlServiceTester according to the composed plan. Do not model GraphQL as a generic REST endpoint."

    def _operation(self, profile: RepoProfile) -> tuple[str, str]:
        assessment = profile.capability_assessment
        nodes = assessment.graph.nodes if assessment and assessment.graph else []
        operation = next((node for node in nodes if node.node_type == "graphql_operation" and node.metadata.get("operation_type") in {"query", "mutation"}), None)
        if operation:
            return str(operation.metadata.get("operation_type") or "query"), operation.name
        return "query", "generatedOperation"
