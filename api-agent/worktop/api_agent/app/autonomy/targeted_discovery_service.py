from __future__ import annotations

import hashlib
from pathlib import Path

from worktop.api_agent.app.autonomy.detectors.helpers import iter_source_files
from worktop.api_agent.app.schemas.autonomy import (
    CapabilityRecord,
    DiscoveryRequest,
    EvidenceRecord,
    EvidenceType,
    GraphEdge,
    GraphNode,
)


class TargetedDiscoveryService:
    """Executes bounded evidence requests without giving the model write authority."""

    def __init__(self, max_files_per_request: int = 400, max_matches_per_request: int = 40) -> None:
        self.max_files_per_request = max_files_per_request
        self.max_matches_per_request = max_matches_per_request

    def discover(self, root: Path, revision: str, requests: list[DiscoveryRequest]):
        evidence: list[EvidenceRecord] = []
        capabilities: list[CapabilityRecord] = []
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        searched: set[tuple[str, str]] = set()
        for request in requests:
            matches = 0
            for path in iter_source_files(root, {".java", ".kt", ".py", ".xml", ".gradle", ".kts", ".graphql", ".graphqls", ".proto"}, self.max_files_per_request):
                relative = str(path.relative_to(root))
                if not self._matches_patterns(relative, request.file_patterns):
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")[:150000]
                for symbol in request.search_symbols:
                    key = (relative, symbol)
                    if key in searched or symbol.lower() not in text.lower():
                        continue
                    searched.add(key); matches += 1
                    line = text.lower()[: text.lower().index(symbol.lower())].count("\n") + 1
                    capability = self._capability_for(symbol, request.target_capability)
                    evidence_id = f"ev-{hashlib.sha256(f'targeted|{relative}|{symbol}|{revision}'.encode()).hexdigest()[:16]}"
                    confidence = 1.0 if self._is_test_path(relative) else 0.88
                    item = EvidenceRecord(
                        evidence_id=evidence_id,
                        capability=capability,
                        evidence_type=EvidenceType.EXISTING_TEST if self._is_test_path(relative) else EvidenceType.SOURCE_USAGE,
                        source_file=relative,
                        start_line=line,
                        end_line=line,
                        signal=f"Targeted discovery found {symbol} for: {request.question}",
                        confidence=confidence,
                        detector="targeted_discovery",
                        repository_revision=revision,
                    )
                    evidence.append(item)
                    category = "test_mechanism" if self._is_test_mechanism(capability) else request.target_capability
                    capabilities.append(CapabilityRecord(capability_id=capability, category=category, name=capability, confidence=confidence, evidence_ids=[evidence_id]))
                    file_id = f"file:{relative}"; capability_id = f"capability:{capability}"
                    nodes.extend([GraphNode(node_id=file_id, node_type="test_file" if self._is_test_path(relative) else "source_file", name=path.name, path=relative), GraphNode(node_id=capability_id, node_type="capability", name=capability)])
                    edges.append(GraphEdge(source_id=file_id, target_id=capability_id, edge_type="targeted_evidence", evidence_ids=[evidence_id], confidence=confidence))
                    if matches >= self.max_matches_per_request:
                        break
                if matches >= self.max_matches_per_request:
                    break
        return evidence, capabilities, nodes, edges

    def _matches_patterns(self, path: str, patterns: list[str]) -> bool:
        if not patterns:
            return True
        lowered = path.lower()
        # Discovery patterns are intent hints, not a glob-security boundary. Include
        # production source when no tests exist so source can guide strategy composition.
        if "src/main/" in lowered:
            return True
        return any(token in lowered for token in ("/test/", "tests/", "integrationtest"))

    def _is_test_path(self, path: str) -> bool:
        lowered = path.lower()
        return any(token in lowered for token in ("/test/", "tests/", "integrationtest"))

    def _capability_for(self, symbol: str, fallback: str) -> str:
        normalized = {
            "MockMvc": "mockmvc", "WebTestClient": "webtestclient", "RestAssured": "rest_assured",
            "GraphQlTester": "graphql_tester", "HttpGraphQlTester": "http_graphql_tester",
            "InProcessServerBuilder": "grpc_in_process", "MockWebServer": "mockwebserver",
            "WireMock": "wiremock", "StepVerifier": "step_verifier", "WebClient": "spring_webclient",
        }
        return normalized.get(symbol, fallback)

    def _is_test_mechanism(self, capability: str) -> bool:
        return capability in {"mockmvc", "webtestclient", "rest_assured", "graphql_tester", "http_graphql_tester", "grpc_in_process", "step_verifier"}
