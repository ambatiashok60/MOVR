from __future__ import annotations

from worktop.api_agent.app.schemas.autonomy import CapabilityRecord, EvidenceGraph, EvidenceRecord, GraphEdge, GraphNode


class EvidenceCatalog:
    def merge(self, revision: str, versions: dict[str, str], evidence: list[EvidenceRecord], capabilities: list[CapabilityRecord], nodes: list[GraphNode], edges: list[GraphEdge]):
        evidence_by_id = {item.evidence_id: item for item in evidence}
        capabilities_by_id: dict[str, CapabilityRecord] = {}
        for item in capabilities:
            existing = capabilities_by_id.get(item.capability_id)
            if existing is None:
                capabilities_by_id[item.capability_id] = item.model_copy(deep=True)
            else:
                existing.evidence_ids = list(dict.fromkeys([*existing.evidence_ids, *item.evidence_ids]))
                existing.confidence = max(existing.confidence, item.confidence)
        node_by_id = {item.node_id: item for item in nodes}
        edge_by_key = {(item.source_id, item.target_id, item.edge_type): item for item in edges}
        graph = EvidenceGraph(repository_revision=revision, detector_versions=versions, nodes=list(node_by_id.values()), edges=list(edge_by_key.values()))
        return list(evidence_by_id.values()), list(capabilities_by_id.values()), graph
