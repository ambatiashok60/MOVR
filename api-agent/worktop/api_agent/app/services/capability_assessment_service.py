from __future__ import annotations

import hashlib
from pathlib import Path

from worktop.api_agent.app.autonomy.cache import CapabilityAssessmentCache
from worktop.api_agent.app.autonomy.detectors import CapabilityDetectorRegistry
from worktop.api_agent.app.autonomy.detectors.base import DetectorContext
from worktop.api_agent.app.autonomy.evidence_catalog import EvidenceCatalog
from worktop.api_agent.app.schemas.autonomy import (
    CapabilityAssessment,
    CapabilityRecord,
    AutonomyTelemetry,
    DiscoveryRequest,
    EvidenceRecord,
    EvidenceType,
    PhaseTransition,
    ReadinessStatus,
    StageDecision,
    TestingTopology,
    TransportNode,
)
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.utils.logging_utils import log_step


class CapabilityAssessmentService:
    """Builds the first autonomous decision artifact from deterministic repo evidence.

    Milestone 1 intentionally runs in shadow mode: it reports whether strategy planning
    is ready but does not replace the legacy StrategyRegistry yet.
    """

    _shared_cache = CapabilityAssessmentCache()

    def __init__(self, registry: CapabilityDetectorRegistry | None = None, cache: CapabilityAssessmentCache | None = None) -> None:
        self.registry = registry or CapabilityDetectorRegistry()
        self.cache = cache or self._shared_cache
        self.catalog = EvidenceCatalog()

    def assess(self, profile: RepoProfile) -> CapabilityAssessment:
        root = Path(profile.repo_path)
        versions = self.registry.versions()
        revision = self.cache.revision(root, versions)
        cached = self.cache.get(revision)
        if cached is not None:
            if cached.telemetry:
                cached.telemetry.cache_hit = True
            return cached

        detected = self.registry.detect(DetectorContext(root=root, profile=profile, repository_revision=revision))
        evidence, capabilities, graph = self.catalog.merge(revision, versions, detected.evidence, detected.capabilities, detected.nodes, detected.edges)

        # Preserve legacy profile facts as compatibility evidence while detector plugins
        # become the primary source of autonomous capability decisions.
        for language in profile.languages:
            self._add(evidence, capabilities, "language", language, EvidenceType.SOURCE_USAGE, f"{language} source files detected", 0.9)
        for framework in profile.service_frameworks:
            self._add(evidence, capabilities, "framework", framework, EvidenceType.SOURCE_USAGE, f"Framework usage detected: {framework}", 0.9)
        for style in profile.api_styles:
            evidence_type = EvidenceType.SCHEMA if style in {"graphql", "openapi"} else EvidenceType.SOURCE_USAGE
            self._add(evidence, capabilities, "transport", style, evidence_type, f"API style detected: {style}", 0.8)
        for framework in profile.test_frameworks:
            self._add(evidence, capabilities, "test_mechanism", framework, EvidenceType.EXISTING_TEST, f"Testing mechanism detected: {framework}", 1.0)
        for framework in profile.mocking_frameworks:
            self._add(evidence, capabilities, "mock_mechanism", framework, EvidenceType.EXISTING_TEST, f"Mocking mechanism detected: {framework}", 0.95)
        for endpoint in profile.endpoints:
            self._add(evidence, capabilities, "operation", f"{endpoint.method} {endpoint.path}", EvidenceType.SOURCE_USAGE, "Endpoint source mapping", 0.9, endpoint.source_file)

        strategy = profile.team_strategy
        for schema_path in strategy.graphql_schema_files:
            self._add(evidence, capabilities, "schema", "graphql_schema", EvidenceType.SCHEMA, "GraphQL schema file detected", 0.8, schema_path)
        for command in strategy.validation_commands:
            self._add(evidence, capabilities, "validation", "validation_command", EvidenceType.COMMAND, command, 0.95)

        detected_names = {item.name for item in capabilities if item.detected}
        application_frameworks = sorted(name for name in detected_names if name in {"spring_boot", "spring_mvc", "spring_webflux", "fastapi", "django", "flask"})
        transport_names = sorted(name for name in detected_names if name in {"rest", "openapi", "graphql", "spring_graphql", "grpc", "grpc_server", "grpc_stream"})
        test_mechanisms = sorted(name for name in detected_names if any(token in name for token in ("junit", "mockmvc", "webtestclient", "rest_assured", "graphql_tester", "grpc_in_process", "step_verifier", "pytest", "httpx", "testclient")))
        mock_mechanisms = sorted(name for name in detected_names if name in {"mockito", "wiremock", "mockwebserver", "testcontainers", "respx", "responses"})
        topology = TestingTopology(
            application_frameworks=application_frameworks or list(profile.service_frameworks),
            inbound_transports=[
                TransportNode(name=style, confidence=self._capability_confidence(capabilities, style), evidence_ids=self._ids(capabilities, style))
                for style in (transport_names or profile.api_styles)
            ],
            reactive_model="reactor" if "reactor" in detected_names or self._repo_contains(profile.repo_path, ("Mono<", "Flux<", "reactor.core")) else None,
            existing_test_mechanisms=test_mechanisms or list(profile.test_frameworks),
            mocking_mechanisms=mock_mechanisms or list(profile.mocking_frameworks),
            test_locations=[*strategy.api_test_locations, *strategy.stage_test_locations],
            validation_commands=list(strategy.validation_commands),
        )
        topology.unresolved_edges = self._unresolved(topology, profile)
        topology.confidence = self._topology_confidence(topology)
        readiness = self._readiness(evidence, topology)
        transition = PhaseTransition(
            from_stage="capability_assessment",
            to_stage=readiness.recommended_next_stage,
            outcome=readiness.status,
            reason=(readiness.review_reasons or readiness.unresolved_questions or ["Capability assessment complete."])[0],
            evidence_ids=readiness.evidence_ids,
        )
        assessment = CapabilityAssessment(
            evidence=evidence,
            capabilities=capabilities,
            topology=topology,
            readiness=readiness,
            transitions=[transition],
            shadow_mode=True,
            graph=graph,
            telemetry=AutonomyTelemetry(cache_hit=False, repository_revision=revision, detector_runs=list(self.registry.last_metrics), evidence_count=len(evidence), capability_count=len(capabilities), graph_node_count=len(graph.nodes), graph_edge_count=len(graph.edges)),
        )
        self.cache.put(revision, assessment)
        log_step("capability_assessment_completed", {"repository_revision": revision, "cache_hit": False, "detector_count": len(self.registry.last_metrics), "evidence_count": len(evidence), "capability_count": len(capabilities), "graph_nodes": len(graph.nodes), "graph_edges": len(graph.edges), "readiness": assessment.readiness.status.value})
        return assessment

    def _readiness(self, evidence: list[EvidenceRecord], topology: TestingTopology) -> StageDecision:
        unresolved = list(topology.unresolved_edges)
        requests: list[DiscoveryRequest] = []
        if not topology.existing_test_mechanisms:
            requests.append(DiscoveryRequest(
                question="Which repository-native test mechanism best matches the application source?",
                target_capability="test_mechanism",
                search_symbols=["MockMvc", "WebTestClient", "RestAssured", "GraphQlTester", "InProcessServerBuilder"],
                file_patterns=["src/test/**/*", "src/integrationTest/**/*"],
                preferred_tools=["dependency_scanner", "source_search", "test_scanner"],
                reason="No existing test mechanism was found; source and build evidence must determine the strategy.",
            ))
        status = ReadinessStatus.READY
        next_stage = "strategy_composition"
        review_reasons: list[str] = []
        if unresolved:
            status = ReadinessStatus.NEEDS_MORE_EVIDENCE
            next_stage = "targeted_discovery"
        if len(topology.inbound_transports) > 1 and topology.confidence < 0.8:
            status = ReadinessStatus.NEEDS_REVIEW
            next_stage = None
            review_reasons.append("Multiple API transports were detected without a sufficiently strong testing convention.")
        return StageDecision(
            stage="capability_assessment",
            status=status,
            confidence=topology.confidence,
            evidence_ids=[item.evidence_id for item in evidence],
            unresolved_questions=unresolved,
            recommended_next_stage=next_stage,
            requested_discovery=requests,
            review_reasons=review_reasons,
        )

    def reassess(self, profile: RepoProfile, assessment: CapabilityAssessment) -> CapabilityAssessment:
        names = {item.name for item in assessment.capabilities if item.detected}
        test_mechanisms = sorted(name for name in names if any(token in name for token in ("junit", "mockmvc", "webtestclient", "rest_assured", "graphql_tester", "grpc_in_process", "step_verifier", "pytest", "httpx", "testclient")))
        mock_mechanisms = sorted(name for name in names if name in {"mockito", "wiremock", "mockwebserver", "testcontainers", "respx", "responses"})
        assessment.topology.existing_test_mechanisms = test_mechanisms
        assessment.topology.mocking_mechanisms = mock_mechanisms
        assessment.topology.unresolved_edges = self._unresolved(assessment.topology, profile)
        assessment.topology.confidence = self._topology_confidence(assessment.topology)
        assessment.readiness = self._readiness(assessment.evidence, assessment.topology)
        return assessment

    def _unresolved(self, topology: TestingTopology, profile: RepoProfile) -> list[str]:
        unresolved: list[str] = []
        if not topology.application_frameworks:
            unresolved.append("Application framework is not yet resolved.")
        if not topology.inbound_transports:
            unresolved.append("Inbound API transport is not yet resolved.")
        if not topology.existing_test_mechanisms:
            unresolved.append("No existing repository test mechanism was found.")
        if not topology.test_locations:
            unresolved.append("Test placement convention is not yet resolved.")
        if "graphql" in profile.api_styles and not any("graphql" in item.lower() for item in profile.test_frameworks):
            unresolved.append("GraphQL was detected but no GraphQL testing mechanism was found.")
        return unresolved

    def _topology_confidence(self, topology: TestingTopology) -> float:
        critical = [
            1.0 if topology.application_frameworks else 0.0,
            1.0 if topology.inbound_transports else 0.0,
            1.0 if topology.existing_test_mechanisms else 0.35,
            1.0 if topology.test_locations else 0.4,
        ]
        return round(sum(critical) / len(critical), 2)

    def _add(self, evidence, capabilities, category, name, evidence_type, signal, confidence, source_file=None) -> None:
        raw = f"{category}|{name}|{source_file or ''}|{signal}"
        evidence_id = f"ev-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"
        evidence.append(EvidenceRecord(evidence_id=evidence_id, capability=name, evidence_type=evidence_type, source_file=source_file, signal=signal, confidence=confidence, detector="milestone1_profile_adapter"))
        existing = next((item for item in capabilities if item.capability_id == name), None)
        if existing:
            existing.evidence_ids.append(evidence_id)
            existing.confidence = max(existing.confidence, confidence)
        else:
            capabilities.append(CapabilityRecord(capability_id=name, category=category, name=name, confidence=confidence, evidence_ids=[evidence_id]))

    def _ids(self, capabilities, name):
        item = next((candidate for candidate in capabilities if candidate.name == name), None)
        return list(item.evidence_ids) if item else []

    def _capability_confidence(self, capabilities, name):
        item = next((candidate for candidate in capabilities if candidate.name == name), None)
        return item.confidence if item else 0.5

    def _repo_contains(self, repo_path: str, needles: tuple[str, ...]) -> bool:
        root = Path(repo_path)
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".java", ".kt"} or any(part in {".git", "build", "target"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")[:50000]
            if any(needle in text for needle in needles):
                return True
        return False
