from pathlib import Path

from worktop.api_agent.app.schemas.autonomy import ReadinessStatus
from worktop.api_agent.app.services.api_repo_context_service import ApiRepoContextService


def test_java_source_and_existing_tests_produce_ready_capability_profile(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("<dependency>org.springframework.boot</dependency>")
    source = tmp_path / "src/main/java/OrdersController.java"
    source.parent.mkdir(parents=True)
    source.write_text('@RestController class OrdersController { @GetMapping("/api/orders") void get() {} }')
    test = tmp_path / "src/test/java/OrdersControllerTest.java"
    test.parent.mkdir(parents=True)
    test.write_text("class OrdersControllerTest { MockMvc mvc; org.junit.jupiter.api.Test test; }")

    profile = ApiRepoContextService().build(str(tmp_path))

    assert "java" in profile.languages
    assert "spring_boot" in profile.service_frameworks
    assert profile.capability_assessment is not None
    assert profile.capability_assessment.shadow_mode is True
    assert any(item.name == "mockmvc" for item in profile.capability_assessment.capabilities)
    assert profile.capability_assessment.readiness.status == ReadinessStatus.READY
    assert profile.capability_assessment.readiness.recommended_next_stage == "strategy_composition"


def test_missing_tests_requests_targeted_discovery_from_source(tmp_path: Path) -> None:
    (tmp_path / "build.gradle").write_text("implementation 'org.springframework.boot:spring-boot-starter-webflux'")
    source = tmp_path / "src/main/java/PaymentClient.java"
    source.parent.mkdir(parents=True)
    source.write_text("class PaymentClient { WebClient client; Mono<String> call() { return null; } }")

    profile = ApiRepoContextService().build(str(tmp_path))
    assessment = profile.capability_assessment

    assert assessment is not None
    assert assessment.discovery_rounds == 1
    assert assessment.readiness.status == ReadinessStatus.NEEDS_REVIEW
    assert assessment.stopped_reason == "Targeted discovery would repeat the previous request without new evidence." or assessment.stopped_reason == "No new evidence was found."
    assert assessment.topology.reactive_model == "reactor"


def test_graphql_without_graphql_tester_is_not_silently_ready(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("org.springframework.boot")
    schema = tmp_path / "src/main/resources/schema.graphqls"
    schema.parent.mkdir(parents=True)
    schema.write_text("type Query { employee(id: ID!): Employee }")
    source = tmp_path / "src/main/java/EmployeeController.java"
    source.parent.mkdir(parents=True)
    source.write_text("class EmployeeController {}")

    assessment = ApiRepoContextService().build(str(tmp_path)).capability_assessment

    assert assessment is not None
    assert any("GraphQL" in question for question in assessment.readiness.unresolved_questions)
    assert assessment.readiness.status in {ReadinessStatus.NEEDS_MORE_EVIDENCE, ReadinessStatus.NEEDS_REVIEW}


def test_detector_graph_contains_java_source_edges(tmp_path: Path) -> None:
    (tmp_path / "build.gradle").write_text("implementation 'org.springframework.boot:spring-boot-starter-webflux'")
    source = tmp_path / "src/main/java/PaymentClient.java"
    source.parent.mkdir(parents=True)
    source.write_text("import org.springframework.web.reactive.function.client.WebClient; class PaymentClient { WebClient client; }")

    assessment = ApiRepoContextService().build(str(tmp_path)).capability_assessment

    assert assessment is not None and assessment.graph is not None
    assert any(item.name == "spring_webclient" for item in assessment.capabilities)
    assert any(edge.edge_type == "uses" for edge in assessment.graph.edges)
    assert "java_source_capability" in assessment.graph.detector_versions


def test_revision_cache_reuses_unchanged_detector_assessment(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("org.springframework.boot junit-jupiter")
    source = tmp_path / "src/main/java/App.java"
    source.parent.mkdir(parents=True)
    source.write_text("@SpringBootApplication class App {}")
    service = ApiRepoContextService()

    first = service.build(str(tmp_path)).capability_assessment
    second = service.build(str(tmp_path)).capability_assessment

    assert first is not None and first.cache_hit is False
    assert second is not None and second.cache_hit is True
    assert first.graph is not None and second.graph is not None
    assert first.graph.repository_revision == second.graph.repository_revision


def test_targeted_discovery_finds_existing_webtestclient_and_advances(tmp_path: Path) -> None:
    (tmp_path / "build.gradle").write_text("implementation 'org.springframework.boot:spring-boot-starter-webflux'")
    source = tmp_path / "src/main/java/OrdersHandler.java"
    source.parent.mkdir(parents=True)
    source.write_text("class OrdersHandler { reactor.core.publisher.Mono<String> get() { return null; } }")
    test = tmp_path / "src/integrationTest/java/OrdersHandlerIT.java"
    test.parent.mkdir(parents=True)
    test.write_text("class OrdersHandlerIT { WebTestClient client; }")

    assessment = ApiRepoContextService().build(str(tmp_path)).capability_assessment

    assert assessment is not None
    assert "webtestclient" in assessment.topology.existing_test_mechanisms
    assert assessment.readiness.status == ReadinessStatus.READY
    assert assessment.readiness.recommended_next_stage == "strategy_composition"
    assert any(item.from_stage == "targeted_discovery" for item in assessment.transitions) or assessment.discovery_rounds == 0
