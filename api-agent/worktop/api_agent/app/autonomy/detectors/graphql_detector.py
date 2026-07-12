from __future__ import annotations

import re

from worktop.api_agent.app.autonomy.detectors.base import DetectorContext, DetectorResult
from worktop.api_agent.app.autonomy.detectors.helpers import create_detection, iter_source_files
from worktop.api_agent.app.schemas.autonomy import EvidenceType, GraphEdge, GraphNode


class SpringGraphQLCapabilityDetector:
    detector_name = "spring_graphql_capability"
    detector_version = "1.0.0"

    TYPE_BLOCK = re.compile(r"\btype\s+(Query|Mutation|Subscription)\s*\{(.*?)\}", re.DOTALL)
    FIELD = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(\([^)]*\))?\s*:\s*([^#\n]+)", re.MULTILINE)
    RESOLVER = re.compile(r"@(QueryMapping|MutationMapping|SubscriptionMapping|SchemaMapping)(?:\(\s*(?:name\s*=\s*)?[\"']([^\"']+)[\"']\s*\))?[\s\S]{0,300}?(?:public\s+)?[\w<>?,.\[\]\s]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")

    def supports(self, context: DetectorContext) -> bool:
        return "java" in context.profile.languages or bool(context.profile.team_strategy.graphql_schema_files)

    def detect(self, context: DetectorContext) -> DetectorResult:
        result = DetectorResult()
        operations: dict[tuple[str, str], str] = {}
        for path in iter_source_files(context.root, {".graphql", ".graphqls"}):
            text = path.read_text(encoding="utf-8", errors="ignore")
            relative = str(path.relative_to(context.root)); schema_id = f"schema:{relative}"
            result.nodes.append(GraphNode(node_id=schema_id, node_type="graphql_schema", name=path.name, path=relative))
            evidence, record = create_detection(self.detector_name, context.repository_revision, "transport", "spring_graphql", EvidenceType.SCHEMA, "GraphQL executable schema detected", 0.9, path)
            result.evidence.append(evidence); result.capabilities.append(record)
            for operation_type, body in self.TYPE_BLOCK.findall(text):
                for name, arguments, return_type in self.FIELD.findall(body):
                    operation_id = f"graphql:{operation_type.lower()}:{name}"
                    operations[(operation_type.lower(), name)] = operation_id
                    result.nodes.append(GraphNode(node_id=operation_id, node_type="graphql_operation", name=name, path=relative, metadata={"operation_type": operation_type.lower(), "arguments": arguments or "", "return_type": return_type.strip()}))
                    result.edges.append(GraphEdge(source_id=schema_id, target_id=operation_id, edge_type="declares", evidence_ids=[evidence.evidence_id], confidence=0.95))
        for path in iter_source_files(context.root, {".java", ".kt"}):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "Mapping" not in text:
                continue
            relative = str(path.relative_to(context.root)); file_id = f"file:{relative}"
            result.nodes.append(GraphNode(node_id=file_id, node_type="source_file", name=path.name, path=relative))
            for annotation, explicit_name, method_name in self.RESOLVER.findall(text):
                operation_type = {"QueryMapping": "query", "MutationMapping": "mutation", "SubscriptionMapping": "subscription", "SchemaMapping": "field"}[annotation]
                operation_name = explicit_name or method_name
                resolver_id = f"resolver:{relative}:{method_name}"
                result.nodes.append(GraphNode(node_id=resolver_id, node_type="graphql_resolver", name=method_name, path=relative, metadata={"annotation": annotation, "operation_name": operation_name}))
                result.edges.append(GraphEdge(source_id=file_id, target_id=resolver_id, edge_type="declares", confidence=0.95))
                target = operations.get((operation_type, operation_name))
                if target:
                    result.edges.append(GraphEdge(source_id=resolver_id, target_id=target, edge_type="implements", confidence=0.92))
                else:
                    unresolved_id = f"graphql:{operation_type}:{operation_name}"
                    result.nodes.append(GraphNode(node_id=unresolved_id, node_type="graphql_operation", name=operation_name, metadata={"operation_type": operation_type}))
                    result.edges.append(GraphEdge(source_id=resolver_id, target_id=unresolved_id, edge_type="implements", confidence=0.65, resolution="inferred"))
        return result
