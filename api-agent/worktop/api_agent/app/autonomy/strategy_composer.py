from __future__ import annotations

from typing import Protocol

from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.strategy_composition import (
    DependencySubstitution,
    StrategyCandidate,
    TestGenerationPlan,
)


class StrategyCapabilityProvider(Protocol):
    provider_name: str
    def candidates(self, profile: RepoProfile) -> list[StrategyCandidate]: ...
    def plan(self, profile: RepoProfile, candidate: StrategyCandidate) -> TestGenerationPlan: ...


class WebFluxWebClientCapabilityProvider:
    provider_name = "spring_webflux_webclient"

    def candidates(self, profile: RepoProfile) -> list[StrategyCandidate]:
        assessment = profile.capability_assessment
        if assessment is None:
            return []
        names = {item.name for item in assessment.capabilities}
        evidence_ids = [item.evidence_id for item in assessment.evidence if item.capability in {"spring_webflux", "spring_webclient", "webtestclient", "mockwebserver", "wiremock", "reactor", "step_verifier"}]
        candidates: list[StrategyCandidate] = []
        if "spring_webflux" in names or assessment.topology.reactive_model == "reactor":
            established = "webtestclient" in names
            candidates.append(StrategyCandidate(
                strategy_name="java_spring_webtestclient",
                compatible=True,
                confidence=0.96 if established else 0.72,
                required_capabilities=["spring_webflux", "webtestclient"],
                evidence_ids=evidence_ids,
                reasons=["Reactive Spring source was detected.", *( ["Existing WebTestClient tests were detected."] if established else ["WebTestClient is the Spring-native reactive HTTP test driver."] )],
                warnings=[] if established else ["No existing WebTestClient convention was found; the driver is derived from Spring WebFlux source."],
            ))
        return candidates

    def plan(self, profile: RepoProfile, candidate: StrategyCandidate) -> TestGenerationPlan:
        assessment = profile.capability_assessment
        names = {item.name for item in assessment.capabilities} if assessment else set()
        substitutions: list[DependencySubstitution] = []
        review: list[str] = list(candidate.warnings)
        if "spring_webclient" in names:
            if "mockwebserver" in names:
                mechanism, source, confidence, approval = "mockwebserver", "existing_repository", 1.0, False
            elif "wiremock" in names:
                mechanism, source, confidence, approval = "wiremock", "existing_repository", 0.95, False
            else:
                mechanism, source, confidence, approval = "mockwebserver", "source_derived_recommendation", 0.68, True
                review.append("WebClient is active but no repository-native HTTP stub mechanism exists; adding MockWebServer requires review.")
            substitutions.append(DependencySubstitution(dependency_capability="spring_webclient", mechanism=mechanism, source=source, confidence=confidence, approval_required=approval, reasons=["Exercise the real WebClient rather than deep-stubbing its fluent chain."]))
        return TestGenerationPlan(
            status="ready" if not review else "needs_review",
            bootstrap="spring_boot_webflux_test",
            inbound_driver="webtestclient",
            reactive_model="reactor",
            dependency_substitutions=substitutions,
            fixture_strategy="reuse_repository_fixtures",
            assertion_strategy="webtestclient_response_assertions",
            cleanup_strategy="close_http_stub_and_reset_test_data",
            validation_commands=list(profile.team_strategy.validation_commands),
            selected_strategy=candidate.strategy_name,
            confidence=candidate.confidence,
            evidence_ids=candidate.evidence_ids,
            candidates=[candidate],
            review_reasons=review,
        )


class CapabilityStrategyComposer:
    def __init__(self, providers: list[StrategyCapabilityProvider] | None = None) -> None:
        self.providers = providers or [GrpcCapabilityProvider(), SpringGraphQLCapabilityProvider(), WebFluxWebClientCapabilityProvider()]

    def compose(self, profile: RepoProfile) -> TestGenerationPlan | None:
        candidates = [candidate for provider in self.providers for candidate in provider.candidates(profile) if candidate.compatible]
        if not candidates:
            return None
        selected = sorted(candidates, key=lambda item: item.confidence, reverse=True)[0]
        provider = next(item for item in self.providers if any(candidate.strategy_name == selected.strategy_name for candidate in item.candidates(profile)))
        plan = provider.plan(profile, selected)
        plan.candidates = sorted(candidates, key=lambda item: item.confidence, reverse=True)
        return plan


class SpringGraphQLCapabilityProvider:
    provider_name = "spring_graphql"

    def candidates(self, profile: RepoProfile) -> list[StrategyCandidate]:
        assessment = profile.capability_assessment
        if assessment is None:
            return []
        names = {item.name for item in assessment.capabilities}
        if not ({"graphql", "spring_graphql"} & names):
            return []
        driver = next((name for name in ("http_graphql_tester", "web_graphql_tester", "execution_graphql_tester", "graphql_tester") if name in names), None)
        evidence_ids = [item.evidence_id for item in assessment.evidence if "graphql" in item.capability]
        confidence = 0.97 if driver else 0.7
        return [StrategyCandidate(
            strategy_name="java_spring_graphql_tester",
            compatible="java" in profile.languages and "spring_graphql" in names,
            confidence=confidence,
            required_capabilities=["spring_graphql", driver or "http_graphql_tester"],
            evidence_ids=evidence_ids,
            reasons=["Spring GraphQL schema/resolver evidence was detected.", *([f"Existing {driver} convention was detected."] if driver else ["HttpGraphQlTester is the Spring-native HTTP integration driver."])],
            warnings=[] if driver else ["No existing GraphQlTester convention was found; HttpGraphQlTester is source-derived and requires review."],
        )]

    def plan(self, profile: RepoProfile, candidate: StrategyCandidate) -> TestGenerationPlan:
        assessment = profile.capability_assessment
        names = {item.name for item in assessment.capabilities} if assessment else set()
        driver = next((name for name in ("http_graphql_tester", "web_graphql_tester", "execution_graphql_tester", "graphql_tester") if name in names), "http_graphql_tester")
        review = list(candidate.warnings)
        operation_count = len([node for node in (assessment.graph.nodes if assessment and assessment.graph else []) if node.node_type == "graphql_operation"])
        if not operation_count:
            review.append("GraphQL transport was detected but no schema operation could be resolved.")
        return TestGenerationPlan(
            status="ready" if not review else "needs_review",
            bootstrap="spring_graphql_test" if driver != "http_graphql_tester" else "spring_boot_random_port",
            inbound_driver=driver,
            reactive_model="reactor" if any(item.name == "graphql_subscription" for item in (assessment.capabilities if assessment else [])) else None,
            fixture_strategy="reuse_graphql_documents_and_repository_fixtures",
            assertion_strategy="graphql_path_and_error_assertions",
            cleanup_strategy="reset_mutation_state_and_cancel_subscriptions",
            validation_commands=list(profile.team_strategy.validation_commands),
            selected_strategy=candidate.strategy_name,
            confidence=candidate.confidence,
            evidence_ids=candidate.evidence_ids,
            candidates=[candidate],
            review_reasons=review,
        )


class GrpcCapabilityProvider:
    provider_name = "grpc"

    def candidates(self, profile: RepoProfile) -> list[StrategyCandidate]:
        assessment = profile.capability_assessment
        if assessment is None:
            return []
        names = {item.name for item in assessment.capabilities}
        if not ({"grpc", "grpc_server"} & names):
            return []
        in_process = "grpc_in_process" in names
        method_nodes = [node for node in (assessment.graph.nodes if assessment.graph else []) if node.node_type == "grpc_method"]
        evidence_ids = [item.evidence_id for item in assessment.evidence if item.capability.startswith("grpc")]
        return [StrategyCandidate(
            strategy_name="java_grpc_in_process",
            compatible="java" in profile.languages and bool(method_nodes),
            confidence=0.97 if in_process else 0.71,
            required_capabilities=["grpc", "grpc_in_process"],
            evidence_ids=evidence_ids,
            reasons=["Protocol Buffer service methods were discovered.", *(["Existing in-process gRPC tests were detected."] if in_process else ["In-process server/channel testing is the isolated gRPC-native strategy."])],
            warnings=[] if in_process else ["No existing in-process gRPC test convention was found; the strategy requires review."],
        )]

    def plan(self, profile: RepoProfile, candidate: StrategyCandidate) -> TestGenerationPlan:
        assessment = profile.capability_assessment
        method_nodes = [node for node in (assessment.graph.nodes if assessment and assessment.graph else []) if node.node_type == "grpc_method"]
        streams = sorted({str(node.metadata.get("stream_kind")) for node in method_nodes})
        review = list(candidate.warnings)
        if not method_nodes:
            review.append("gRPC was detected but no RPC method could be resolved from proto schemas.")
        return TestGenerationPlan(
            status="ready" if not review else "needs_review",
            bootstrap="grpc_in_process_server",
            inbound_driver="generated_grpc_stub",
            reactive_model="grpc_stream_observer" if any(item != "unary" for item in streams) else None,
            fixture_strategy="protobuf_builders_and_repository_fixtures",
            assertion_strategy="protobuf_response_and_grpc_status_assertions",
            cleanup_strategy="shutdown_channel_and_server",
            validation_commands=list(profile.team_strategy.validation_commands),
            selected_strategy=candidate.strategy_name,
            confidence=candidate.confidence,
            evidence_ids=candidate.evidence_ids,
            candidates=[candidate],
            review_reasons=review,
        )
