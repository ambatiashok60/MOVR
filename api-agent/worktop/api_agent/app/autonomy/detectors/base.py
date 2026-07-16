from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from worktop.api_agent.app.schemas.autonomy import CapabilityRecord, EvidenceRecord, GraphEdge, GraphNode
from worktop.api_agent.app.schemas.repo_profile import RepoProfile


@dataclass(frozen=True)
class DetectorContext:
    root: Path
    profile: RepoProfile
    repository_revision: str


@dataclass
class DetectorResult:
    evidence: list[EvidenceRecord] = field(default_factory=list)
    capabilities: list[CapabilityRecord] = field(default_factory=list)
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


class CapabilityDetector(Protocol):
    detector_name: str
    detector_version: str

    def supports(self, context: DetectorContext) -> bool: ...
    def detect(self, context: DetectorContext) -> DetectorResult: ...
