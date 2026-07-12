from pathlib import Path

import pytest

from worktop.api_agent.app.services.api_repo_context_service import ApiRepoContextService


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)


@pytest.mark.parametrize(
    ("case", "expected_strategy", "expected_driver"),
    [
        ("webflux", "java_spring_webtestclient", "webtestclient"),
        ("graphql", "java_spring_graphql_tester", "http_graphql_tester"),
        ("grpc", "java_grpc_in_process", "generated_grpc_stub"),
    ],
)
def test_golden_repository_capability_and_strategy(case: str, expected_strategy: str, expected_driver: str, tmp_path: Path) -> None:
    if case == "webflux":
        _write(tmp_path, "build.gradle", "spring-boot-starter-webflux junit-jupiter mockwebserver")
        _write(tmp_path, "src/main/java/Client.java", "class Client { WebClient webClient; reactor.core.publisher.Mono<String> call(){return null;} }")
        _write(tmp_path, "src/test/java/ClientIT.java", "class ClientIT { WebTestClient client; MockWebServer server; }")
    elif case == "graphql":
        _write(tmp_path, "build.gradle", "spring-boot-starter-graphql junit-jupiter")
        _write(tmp_path, "src/main/resources/schema.graphqls", "type Query { employee: Employee } type Employee { id: ID! }")
        _write(tmp_path, "src/main/java/Resolver.java", "class Resolver { @QueryMapping Employee employee(){return null;} }")
        _write(tmp_path, "src/test/java/GraphQlIT.java", "class GraphQlIT { HttpGraphQlTester tester; }")
    else:
        _write(tmp_path, "build.gradle", "grpc-netty grpc-protobuf grpc-stub junit-jupiter")
        _write(tmp_path, "src/main/proto/service.proto", "service EmployeeService { rpc GetEmployee (Request) returns (Response); }")
        _write(tmp_path, "src/main/java/GrpcService.java", "@GrpcService class GrpcService extends EmployeeServiceGrpc.EmployeeServiceImplBase {}")
        _write(tmp_path, "src/test/java/GrpcIT.java", "class GrpcIT { InProcessServerBuilder server; InProcessChannelBuilder channel; }")
    profile = ApiRepoContextService().build(str(tmp_path))
    assert profile.generation_plan is not None
    assert profile.generation_plan.selected_strategy == expected_strategy
    assert profile.generation_plan.inbound_driver == expected_driver
    assert profile.capability_assessment is not None
    assert profile.capability_assessment.telemetry is not None
    assert not profile.capability_assessment.telemetry.cache_hit
