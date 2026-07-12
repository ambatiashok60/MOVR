from __future__ import annotations

import re

from worktop.api_agent.app.autonomy.detectors.base import DetectorContext, DetectorResult
from worktop.api_agent.app.autonomy.detectors.helpers import create_detection, iter_source_files
from worktop.api_agent.app.schemas.autonomy import EvidenceType, GraphEdge, GraphNode


class GrpcCapabilityDetector:
    detector_name = "grpc_capability"
    detector_version = "1.0.0"

    SERVICE = re.compile(r"\bservice\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{(.*?)\}", re.DOTALL)
    RPC = re.compile(r"\brpc\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*(stream\s+)?([.A-Za-z_][.A-Za-z0-9_]*)\s*\)\s*returns\s*\(\s*(stream\s+)?([.A-Za-z_][.A-Za-z0-9_]*)\s*\)")
    GRPC_SERVICE = re.compile(r"@GrpcService[\s\S]{0,300}?class\s+([A-Za-z_][A-Za-z0-9_]*)\s+extends\s+([A-Za-z0-9_.]+ImplBase)")

    def supports(self, context: DetectorContext) -> bool:
        return any(path.suffix == ".proto" for path in iter_source_files(context.root, {".proto"}, 1)) or "java" in context.profile.languages

    def detect(self, context: DetectorContext) -> DetectorResult:
        result = DetectorResult(); services: dict[str, str] = {}
        for path in iter_source_files(context.root, {".proto"}):
            text = path.read_text(encoding="utf-8", errors="ignore"); relative = str(path.relative_to(context.root)); schema_id = f"proto:{relative}"
            result.nodes.append(GraphNode(node_id=schema_id, node_type="proto_schema", name=path.name, path=relative))
            evidence, record = create_detection(self.detector_name, context.repository_revision, "transport", "grpc", EvidenceType.SCHEMA, "Protocol Buffer service schema detected", 0.95, path)
            result.evidence.append(evidence); result.capabilities.append(record)
            for service_name, body in self.SERVICE.findall(text):
                service_id = f"grpc_service:{service_name}"; services[service_name] = service_id
                result.nodes.append(GraphNode(node_id=service_id, node_type="grpc_service", name=service_name, path=relative))
                result.edges.append(GraphEdge(source_id=schema_id, target_id=service_id, edge_type="declares", evidence_ids=[evidence.evidence_id], confidence=0.98))
                for method, client_stream, request_type, server_stream, response_type in self.RPC.findall(body):
                    stream_kind = "bidirectional" if client_stream and server_stream else "client_stream" if client_stream else "server_stream" if server_stream else "unary"
                    method_id = f"grpc_method:{service_name}:{method}"
                    result.nodes.append(GraphNode(node_id=method_id, node_type="grpc_method", name=method, path=relative, metadata={"service": service_name, "request_type": request_type, "response_type": response_type, "stream_kind": stream_kind}))
                    result.edges.append(GraphEdge(source_id=service_id, target_id=method_id, edge_type="declares", evidence_ids=[evidence.evidence_id], confidence=0.98))
                    if stream_kind != "unary":
                        stream_evidence, stream_record = create_detection(self.detector_name, context.repository_revision, "transport", f"grpc_{stream_kind}", EvidenceType.SCHEMA, f"gRPC {stream_kind} method detected: {service_name}.{method}", 0.95, path)
                        result.evidence.append(stream_evidence); result.capabilities.append(stream_record)
        for path in iter_source_files(context.root, {".java", ".kt"}):
            text = path.read_text(encoding="utf-8", errors="ignore")
            relative = str(path.relative_to(context.root))
            for class_name, base_name in self.GRPC_SERVICE.findall(text):
                implementation_id = f"grpc_implementation:{relative}:{class_name}"
                result.nodes.append(GraphNode(node_id=implementation_id, node_type="grpc_implementation", name=class_name, path=relative, metadata={"base": base_name}))
                probable_service = base_name.split(".")[-1].removesuffix("GrpcImplBase").removesuffix("ImplBase")
                target = services.get(probable_service)
                if target:
                    result.edges.append(GraphEdge(source_id=implementation_id, target_id=target, edge_type="implements", confidence=0.9))
                else:
                    result.edges.append(GraphEdge(source_id=implementation_id, target_id=f"grpc_service:{probable_service}", edge_type="implements", confidence=0.6, resolution="inferred"))
                evidence, record = create_detection(self.detector_name, context.repository_revision, "transport", "grpc_server", EvidenceType.SOURCE_USAGE, f"Java gRPC service implementation detected: {class_name}", 0.95, path)
                result.evidence.append(evidence); result.capabilities.append(record)
            for signal, capability in (("newBlockingStub", "grpc_blocking_stub"), ("newFutureStub", "grpc_future_stub"), ("newStub", "grpc_async_stub"), ("ManagedChannel", "grpc_client")):
                if signal not in text:
                    continue
                evidence, record = create_detection(self.detector_name, context.repository_revision, "client", capability, EvidenceType.SOURCE_USAGE, f"Generated/client gRPC usage detected: {signal}", 0.9, path)
                result.evidence.append(evidence); result.capabilities.append(record)
        return result
