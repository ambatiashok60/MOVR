from pathlib import Path

from worktop.api_agent.app.services.api_repo_context_service import ApiRepoContextService
from worktop.api_agent.app.strategies.strategy_registry import StrategyRegistry


def _webflux_repo(root: Path, with_test: bool = True, with_mock_server: bool = True) -> None:
    dependencies = "spring-boot-starter-webflux junit-jupiter" + (" mockwebserver" if with_mock_server else "")
    (root / "build.gradle").write_text(dependencies)
    source = root / "src/main/java/PaymentClient.java"
    source.parent.mkdir(parents=True)
    source.write_text("import reactor.core.publisher.Mono; class PaymentClient { WebClient client; Mono<String> pay() { return null; } }")
    if with_test:
        test = root / "src/test/java/PaymentApiTest.java"
        test.parent.mkdir(parents=True)
        stub = " MockWebServer server;" if with_mock_server else ""
        test.write_text(f"class PaymentApiTest {{ WebTestClient client;{stub} }}")


def test_webflux_existing_conventions_compose_high_confidence_plan(tmp_path: Path) -> None:
    _webflux_repo(tmp_path)
    profile = ApiRepoContextService().build(str(tmp_path))
    plan = profile.generation_plan
    assert plan is not None
    assert plan.selected_strategy == "java_spring_webtestclient"
    assert plan.inbound_driver == "webtestclient"
    assert plan.confidence >= 0.9
    assert plan.dependency_substitutions[0].mechanism == "mockwebserver"
    assert plan.dependency_substitutions[0].approval_required is False
    assert StrategyRegistry().select(profile).strategy.strategy_name == "java_spring_webtestclient"


def test_webclient_without_stub_convention_requires_review(tmp_path: Path) -> None:
    _webflux_repo(tmp_path, with_test=True, with_mock_server=False)
    profile = ApiRepoContextService().build(str(tmp_path))
    plan = profile.generation_plan
    assert plan is not None
    assert plan.status == "needs_review"
    assert plan.dependency_substitutions[0].mechanism == "mockwebserver"
    assert plan.dependency_substitutions[0].approval_required is True
    assert any("adding MockWebServer" in reason for reason in plan.review_reasons)
