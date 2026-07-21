from __future__ import annotations

from worktop.api_agent.app.autonomy.detectors.base import DetectorContext, DetectorResult
from worktop.api_agent.app.autonomy.detectors.helpers import create_detection, iter_source_files
from worktop.api_agent.app.schemas.autonomy import EvidenceType, GraphNode


class SchemaTransportDetector:
    detector_name = "schema_transport"
    detector_version = "1.0.0"

    def supports(self, context: DetectorContext) -> bool:
        return True

    def detect(self, context: DetectorContext) -> DetectorResult:
        result = DetectorResult()
        for path in iter_source_files(context.root, {".graphql", ".graphqls", ".proto", ".yaml", ".yml", ".json"}):
            relative = str(path.relative_to(context.root))
            suffix = path.suffix.lower()
            capability = "graphql" if suffix in {".graphql", ".graphqls"} else "grpc" if suffix == ".proto" else None
            if capability is None:
                text = path.read_text(encoding="utf-8", errors="ignore")[:10000].lower()
                capability = "openapi" if "openapi" in text or "swagger" in text else None
            if capability is None:
                continue
            evidence, record = create_detection(self.detector_name, context.repository_revision, "transport", capability, EvidenceType.SCHEMA, f"{capability} schema detected", 0.85, path)
            result.evidence.append(evidence); result.capabilities.append(record)
            result.nodes.append(GraphNode(node_id=f"schema:{relative}", node_type="schema", name=path.name, path=relative))
        return result
