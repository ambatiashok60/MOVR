from pathlib import Path

from worktop.api_agent.app.services.api_repo_context_service import ApiRepoContextService
from worktop.api_agent.app.strategies.strategy_registry import StrategyRegistry


def _graphql_repo(root: Path, with_tester: bool = True) -> None:
    (root / "build.gradle").write_text("spring-boot-starter-graphql junit-jupiter")
    schema = root / "src/main/resources/graphql/schema.graphqls"
    schema.parent.mkdir(parents=True)
    schema.write_text("type Query { employee(id: ID!): Employee }\ntype Mutation { updateEmployee(id: ID!): Employee }\ntype Employee { id: ID! }")
    resolver = root / "src/main/java/EmployeeGraphQlController.java"
    resolver.parent.mkdir(parents=True)
    resolver.write_text("class EmployeeGraphQlController { @QueryMapping Employee employee() { return null; } @MutationMapping Employee updateEmployee() { return null; } }")
    if with_tester:
        test = root / "src/test/java/EmployeeGraphQlTest.java"
        test.parent.mkdir(parents=True)
        test.write_text("class EmployeeGraphQlTest { HttpGraphQlTester graphQlTester; }")


def test_graphql_schema_and_resolver_build_operation_graph(tmp_path: Path) -> None:
    _graphql_repo(tmp_path)
    profile = ApiRepoContextService().build(str(tmp_path))
    assessment = profile.capability_assessment
    assert assessment is not None and assessment.graph is not None
    operations = [node for node in assessment.graph.nodes if node.node_type == "graphql_operation"]
    assert {node.name for node in operations} >= {"employee", "updateEmployee"}
    assert any(edge.edge_type == "implements" and edge.resolution == "resolved" for edge in assessment.graph.edges)


def test_existing_graphql_tester_composes_high_confidence_strategy(tmp_path: Path) -> None:
    _graphql_repo(tmp_path)
    profile = ApiRepoContextService().build(str(tmp_path))
    plan = profile.generation_plan
    assert plan is not None
    assert plan.selected_strategy == "java_spring_graphql_tester"
    assert plan.inbound_driver == "http_graphql_tester"
    assert plan.status == "ready"
    assert plan.confidence >= 0.9
    assert StrategyRegistry().select(profile).strategy.strategy_name == "java_spring_graphql_tester"


def test_graphql_without_tester_derives_strategy_but_requires_review(tmp_path: Path) -> None:
    _graphql_repo(tmp_path, with_tester=False)
    profile = ApiRepoContextService().build(str(tmp_path))
    plan = profile.generation_plan
    assert plan is not None
    assert plan.selected_strategy == "java_spring_graphql_tester"
    assert plan.status == "needs_review"
    assert any("source-derived" in reason for reason in plan.review_reasons)
