from __future__ import annotations

import re

from worktop.api_agent.app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from worktop.api_agent.app.schemas.execution_target import ExecutionTarget
from worktop.api_agent.app.schemas.llm_outputs import GeneratedTestFileOutput
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.strategies.base_strategy import ApiTestGenerationStrategy, StrategyMatch


class JavaGrpcInProcessStrategy(ApiTestGenerationStrategy):
    strategy_name = "java_grpc_in_process"
    target_language = "java"
    test_framework = "junit5_grpc_in_process"

    def supports(self, profile: RepoProfile) -> bool:
        assessment = profile.capability_assessment
        names = {item.name for item in assessment.capabilities} if assessment else set()
        return "java" in profile.languages and bool({"grpc", "grpc_server"} & names)

    def match(self, profile: RepoProfile) -> StrategyMatch:
        assessment = profile.capability_assessment
        names = {item.name for item in assessment.capabilities} if assessment else set()
        established = "grpc_in_process" in names
        return StrategyMatch(self, "high" if established else "medium", ["gRPC proto/service evidence detected.", *(["Existing InProcessServerBuilder tests detected."] if established else [])], [] if established else ["In-process gRPC testing is source-derived and requires review."])

    def fallback_files(self, request: GenerateApiTestCodeRequest, profile: RepoProfile) -> list[GeneratedTestFileOutput]:
        service, method, stream_kind = self._rpc(profile)
        words = re.findall(r"[A-Za-z0-9]+", request.scenario_name)
        class_name = "".join(word[:1].upper() + word[1:] for word in words[:6]) + "GrpcTest"
        method_name = (words[0][:1].lower() + words[0][1:] + "".join(word[:1].upper() + word[1:] for word in words[1:8])) if words else "generatedGrpcScenario"
        content = f'''package generated.api;

import io.grpc.ManagedChannel;
import io.grpc.Server;
import io.grpc.inprocess.InProcessChannelBuilder;
import io.grpc.inprocess.InProcessServerBuilder;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class {class_name} {{
    private Server server;
    private ManagedChannel channel;

    @AfterEach
    void cleanup() {{
        if (channel != null) channel.shutdownNow();
        if (server != null) server.shutdownNow();
    }}

    @Test
    void {method_name}() throws Exception {{
        String serverName = InProcessServerBuilder.generateName();
        server = InProcessServerBuilder.forName(serverName).directExecutor()
            // TODO: add the repository's {service} service implementation.
            .build().start();
        channel = InProcessChannelBuilder.forName(serverName).directExecutor().build();

        // TODO: create the generated {service} stub, call {method} ({stream_kind}),
        // and assert the protobuf response or StatusRuntimeException code.
        assertThat(channel).isNotNull();
    }}
}}
'''
        return [GeneratedTestFileOutput(relative_path=f"src/test/java/generated/api/{class_name}.java", content=content, test_target=str(ExecutionTarget.CI), summary=f"In-process gRPC scaffold for {request.scenario_name}")]

    def prompt_guidance(self, profile: RepoProfile) -> str:
        return "Generate JUnit 5 in-process gRPC tests using the actual generated service/stub classes and protobuf builders. Use InProcessServerBuilder and InProcessChannelBuilder, assert protobuf responses and gRPC status codes, handle unary or streaming semantics from the proto graph, and always close/register server and channel cleanup."

    def _rpc(self, profile: RepoProfile) -> tuple[str, str, str]:
        assessment = profile.capability_assessment
        node = next((item for item in (assessment.graph.nodes if assessment and assessment.graph else []) if item.node_type == "grpc_method"), None)
        if node:
            return str(node.metadata.get("service") or "GeneratedService"), node.name, str(node.metadata.get("stream_kind") or "unary")
        return "GeneratedService", "generatedMethod", "unary"
