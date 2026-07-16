from __future__ import annotations

import re

from worktop.api_agent.app.autonomy.detectors.base import DetectorContext, DetectorResult
from worktop.api_agent.app.autonomy.detectors.helpers import create_detection, iter_source_files
from worktop.api_agent.app.schemas.autonomy import EvidenceType, GraphEdge, GraphNode


class JavaSourceCapabilityDetector:
    detector_name = "java_source_capability"
    detector_version = "1.0.0"

    SIGNALS = {
        "spring_boot": ("@SpringBootApplication", "framework", 0.95),
        "spring_mvc": ("@RestController", "framework", 0.9),
        "spring_webflux": ("RouterFunction", "framework", 0.9),
        "spring_webclient": ("WebClient", "outbound_client", 0.9),
        "reactor": ("reactor.core", "reactive_model", 0.9),
        "spring_graphql": ("@QueryMapping", "transport", 0.95),
        "graphql_mutation": ("@MutationMapping", "transport", 0.95),
        "graphql_subscription": ("@SubscriptionMapping", "transport", 0.95),
        "grpc_server": ("@GrpcService", "transport", 0.95),
        "grpc_client": ("ManagedChannel", "outbound_client", 0.9),
        "grpc_stream": ("StreamObserver", "transport", 0.9),
    }

    def supports(self, context: DetectorContext) -> bool:
        return "java" in context.profile.languages or "kotlin" in context.profile.languages

    def detect(self, context: DetectorContext) -> DetectorResult:
        result = DetectorResult()
        for path in iter_source_files(context.root, {".java", ".kt"}):
            text = path.read_text(encoding="utf-8", errors="ignore")[:100000]
            relative = str(path.relative_to(context.root))
            file_id = f"file:{relative}"
            result.nodes.append(GraphNode(node_id=file_id, node_type="source_file", name=path.name, path=relative))
            for capability, (signal, category, confidence) in self.SIGNALS.items():
                if signal not in text:
                    continue
                line = text[: text.index(signal)].count("\n") + 1
                evidence, record = create_detection(self.detector_name, context.repository_revision, category, capability, EvidenceType.SOURCE_USAGE, f"Java/Kotlin source uses {signal}", confidence, path, line)
                result.evidence.append(evidence); result.capabilities.append(record)
                capability_id = f"capability:{capability}"
                result.nodes.append(GraphNode(node_id=capability_id, node_type="capability", name=capability))
                result.edges.append(GraphEdge(source_id=file_id, target_id=capability_id, edge_type="uses", evidence_ids=[evidence.evidence_id], confidence=confidence))
            for imported in re.findall(r"^import\s+([\w.]+);", text, re.MULTILINE):
                if imported.startswith(("java.", "javax.")):
                    continue
                target = f"symbol:{imported}"
                result.nodes.append(GraphNode(node_id=target, node_type="symbol", name=imported))
                result.edges.append(GraphEdge(source_id=file_id, target_id=target, edge_type="imports", confidence=0.95))
        return result
