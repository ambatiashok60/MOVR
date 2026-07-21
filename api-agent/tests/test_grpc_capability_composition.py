from pathlib import Path

from worktop.api_agent.app.services.api_repo_context_service import ApiRepoContextService
from worktop.api_agent.app.strategies.strategy_registry import StrategyRegistry


def _grpc_repo(root: Path, with_test: bool = True) -> None:
    (root / "build.gradle").write_text("grpc-netty grpc-protobuf grpc-stub junit-jupiter")
    proto = root / "src/main/proto/employee.proto"
    proto.parent.mkdir(parents=True)
    proto.write_text('syntax = "proto3"; service EmployeeService { rpc GetEmployee (GetEmployeeRequest) returns (EmployeeResponse); rpc WatchEmployees (WatchRequest) returns (stream EmployeeResponse); }')
    implementation = root / "src/main/java/EmployeeGrpcService.java"
    implementation.parent.mkdir(parents=True)
    implementation.write_text("@GrpcService class EmployeeGrpcService extends EmployeeServiceGrpc.EmployeeServiceImplBase {}")
    if with_test:
        test = root / "src/test/java/EmployeeGrpcTest.java"
        test.parent.mkdir(parents=True)
        test.write_text("class EmployeeGrpcTest { InProcessServerBuilder server; InProcessChannelBuilder channel; GrpcCleanupRule cleanup; }")


def test_proto_and_java_service_build_grpc_graph(tmp_path: Path) -> None:
    _grpc_repo(tmp_path)
    profile = ApiRepoContextService().build(str(tmp_path))
    assessment = profile.capability_assessment
    assert assessment is not None and assessment.graph is not None
    methods = [node for node in assessment.graph.nodes if node.node_type == "grpc_method"]
    assert {node.name for node in methods} == {"GetEmployee", "WatchEmployees"}
    assert next(node for node in methods if node.name == "WatchEmployees").metadata["stream_kind"] == "server_stream"
    assert any(edge.edge_type == "implements" for edge in assessment.graph.edges)


def test_existing_in_process_convention_composes_high_confidence_grpc_plan(tmp_path: Path) -> None:
    _grpc_repo(tmp_path)
    profile = ApiRepoContextService().build(str(tmp_path))
    plan = profile.generation_plan
    assert plan is not None
    assert plan.selected_strategy == "java_grpc_in_process"
    assert plan.bootstrap == "grpc_in_process_server"
    assert plan.status == "ready"
    assert plan.confidence >= 0.9
    assert plan.reactive_model == "grpc_stream_observer"
    assert StrategyRegistry().select(profile).strategy.strategy_name == "java_grpc_in_process"


def test_grpc_without_existing_test_derives_strategy_and_requires_review(tmp_path: Path) -> None:
    _grpc_repo(tmp_path, with_test=False)
    plan = ApiRepoContextService().build(str(tmp_path)).generation_plan
    assert plan is not None
    assert plan.selected_strategy == "java_grpc_in_process"
    assert plan.status == "needs_review"
    assert any("requires review" in reason for reason in plan.review_reasons)
