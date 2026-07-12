from __future__ import annotations

from worktop.api_agent.app.autonomy.detectors.base import DetectorContext, DetectorResult
from worktop.api_agent.app.autonomy.detectors.helpers import create_detection
from worktop.api_agent.app.schemas.autonomy import EvidenceType, GraphNode


class BuildDependencyDetector:
    detector_name = "build_dependency"
    detector_version = "1.0.0"

    SIGNALS = {
        "spring_boot": ("org.springframework.boot", "framework"),
        "spring_mvc": ("spring-boot-starter-web", "framework"),
        "spring_webflux": ("spring-boot-starter-webflux", "framework"),
        "spring_graphql": ("spring-boot-starter-graphql", "transport"),
        "grpc_java": ("grpc-", "transport"),
        "junit5": ("junit-jupiter", "test_mechanism"),
        "rest_assured": ("rest-assured", "test_mechanism"),
        "wiremock": ("wiremock", "mock_mechanism"),
        "mockwebserver": ("mockwebserver", "mock_mechanism"),
        "reactor_test": ("reactor-test", "test_mechanism"),
        "testcontainers": ("testcontainers", "mock_mechanism"),
    }

    def supports(self, context: DetectorContext) -> bool:
        return any((context.root / name).exists() for name in ("pom.xml", "build.gradle", "build.gradle.kts"))

    def detect(self, context: DetectorContext) -> DetectorResult:
        result = DetectorResult()
        for name in ("pom.xml", "build.gradle", "build.gradle.kts"):
            path = context.root / name
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            result.nodes.append(GraphNode(node_id=f"file:{name}", node_type="build_file", name=name, path=name))
            for capability, (signal, category) in self.SIGNALS.items():
                if signal.lower() not in text:
                    continue
                evidence, record = create_detection(self.detector_name, context.repository_revision, category, capability, EvidenceType.DEPENDENCY, f"Build dependency contains {signal}", 0.75, path)
                result.evidence.append(evidence); result.capabilities.append(record)
        return result
