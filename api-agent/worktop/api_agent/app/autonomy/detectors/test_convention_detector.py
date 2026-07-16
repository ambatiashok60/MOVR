from __future__ import annotations

from worktop.api_agent.app.autonomy.detectors.base import DetectorContext, DetectorResult
from worktop.api_agent.app.autonomy.detectors.helpers import create_detection, iter_source_files
from worktop.api_agent.app.schemas.autonomy import EvidenceType, GraphNode


class ExistingTestConventionDetector:
    detector_name = "existing_test_convention"
    detector_version = "1.0.0"
    SIGNALS = {
        "mockmvc": "MockMvc",
        "webtestclient": "WebTestClient",
        "rest_assured": "RestAssured",
        "http_graphql_tester": "HttpGraphQlTester",
        "web_graphql_tester": "WebGraphQlTester",
        "execution_graphql_tester": "ExecutionGraphQlServiceTester",
        "grpc_in_process": "InProcessServerBuilder",
        "grpc_cleanup": "shutdownNow",
        "step_verifier": "StepVerifier",
        "mockwebserver": "MockWebServer",
        "wiremock": "WireMock",
    }

    def supports(self, context: DetectorContext) -> bool:
        return bool(context.profile.languages)

    def detect(self, context: DetectorContext) -> DetectorResult:
        result = DetectorResult()
        for path in iter_source_files(context.root, {".java", ".kt", ".py"}):
            relative = str(path.relative_to(context.root))
            lowered = relative.lower()
            if not any(part in lowered for part in ("/test/", "tests/", "integrationtest")):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")[:100000]
            result.nodes.append(GraphNode(node_id=f"test:{relative}", node_type="test_file", name=path.name, path=relative))
            for capability, signal in self.SIGNALS.items():
                if signal not in text:
                    continue
                line = text[: text.index(signal)].count("\n") + 1
                category = "mock_mechanism" if capability in {"mockwebserver", "wiremock"} else "test_mechanism"
                evidence, record = create_detection(self.detector_name, context.repository_revision, category, capability, EvidenceType.EXISTING_TEST, f"Existing test uses {signal}", 1.0, path, line)
                result.evidence.append(evidence); result.capabilities.append(record)
        return result
