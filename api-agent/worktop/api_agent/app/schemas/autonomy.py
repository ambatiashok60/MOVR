from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    DEPENDENCY = "dependency"
    SOURCE_USAGE = "source_usage"
    EXISTING_TEST = "existing_test"
    CONFIGURATION = "configuration"
    SCHEMA = "schema"
    COMMAND = "command"
    INFERENCE = "inference"


class ReadinessStatus(str, Enum):
    READY = "ready"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    NEEDS_REVIEW = "needs_review"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class EvidenceRecord(BaseModel):
    evidence_id: str
    capability: str
    evidence_type: EvidenceType
    source_file: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    signal: str
    confidence: float = Field(ge=0.0, le=1.0)
    detector: str
    repository_revision: str | None = None
    file_hash: str | None = None
    resolved: bool = True


class CapabilityRecord(BaseModel):
    capability_id: str
    category: str
    name: str
    detected: bool = True
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    conflicting_capabilities: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)


class TransportNode(BaseModel):
    name: str
    direction: str = "inbound"
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class DependencyNode(BaseModel):
    name: str
    kind: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class TestingTopology(BaseModel):
    application_frameworks: list[str] = Field(default_factory=list)
    inbound_transports: list[TransportNode] = Field(default_factory=list)
    outbound_dependencies: list[DependencyNode] = Field(default_factory=list)
    reactive_model: str | None = None
    existing_test_mechanisms: list[str] = Field(default_factory=list)
    mocking_mechanisms: list[str] = Field(default_factory=list)
    test_locations: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    unresolved_edges: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DiscoveryRequest(BaseModel):
    question: str
    target_capability: str
    search_symbols: list[str] = Field(default_factory=list)
    file_patterns: list[str] = Field(default_factory=list)
    preferred_tools: list[str] = Field(default_factory=list)
    reason: str


class StageDecision(BaseModel):
    stage: str
    status: ReadinessStatus
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    recommended_next_stage: str | None = None
    requested_discovery: list[DiscoveryRequest] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)


class PhaseTransition(BaseModel):
    from_stage: str
    to_stage: str | None = None
    outcome: ReadinessStatus
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CapabilityAssessment(BaseModel):
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    capabilities: list[CapabilityRecord] = Field(default_factory=list)
    topology: TestingTopology = Field(default_factory=TestingTopology)
    readiness: StageDecision
    transitions: list[PhaseTransition] = Field(default_factory=list)
    shadow_mode: bool = True
    graph: EvidenceGraph | None = None
    cache_hit: bool = False
    discovery_rounds: int = 0
    stopped_reason: str | None = None
    telemetry: AutonomyTelemetry | None = None


class GraphNode(BaseModel):
    node_id: str
    node_type: str
    name: str
    path: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source_id: str
    target_id: str
    edge_type: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    resolution: str = "resolved"


class EvidenceGraph(BaseModel):
    repository_revision: str
    detector_versions: dict[str, str] = Field(default_factory=dict)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class DetectorRunMetric(BaseModel):
    detector: str
    version: str
    supported: bool
    duration_ms: float = Field(ge=0.0)
    evidence_count: int = Field(ge=0)
    node_count: int = Field(ge=0)
    error: str | None = None


class AutonomyTelemetry(BaseModel):
    cache_hit: bool = False
    repository_revision: str
    detector_runs: list[DetectorRunMetric] = Field(default_factory=list)
    evidence_count: int = 0
    capability_count: int = 0
    graph_node_count: int = 0
    graph_edge_count: int = 0
    discovery_rounds: int = 0


CapabilityAssessment.model_rebuild()
