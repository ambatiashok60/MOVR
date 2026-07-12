from __future__ import annotations

from time import perf_counter

from worktop.api_agent.app.autonomy.detectors.base import CapabilityDetector, DetectorContext, DetectorResult
from worktop.api_agent.app.autonomy.detectors.build_dependency_detector import BuildDependencyDetector
from worktop.api_agent.app.autonomy.detectors.java_source_detector import JavaSourceCapabilityDetector
from worktop.api_agent.app.autonomy.detectors.schema_detector import SchemaTransportDetector
from worktop.api_agent.app.autonomy.detectors.test_convention_detector import ExistingTestConventionDetector
from worktop.api_agent.app.autonomy.detectors.graphql_detector import SpringGraphQLCapabilityDetector
from worktop.api_agent.app.autonomy.detectors.grpc_detector import GrpcCapabilityDetector
from worktop.api_agent.app.schemas.autonomy import DetectorRunMetric


class CapabilityDetectorRegistry:
    def __init__(self, detectors: list[CapabilityDetector] | None = None) -> None:
        self._detectors = detectors or [BuildDependencyDetector(), JavaSourceCapabilityDetector(), SchemaTransportDetector(), SpringGraphQLCapabilityDetector(), GrpcCapabilityDetector(), ExistingTestConventionDetector()]
        self.last_metrics: list[DetectorRunMetric] = []

    def register(self, detector: CapabilityDetector) -> None:
        self._detectors = [item for item in self._detectors if item.detector_name != detector.detector_name]
        self._detectors.append(detector)

    def versions(self) -> dict[str, str]:
        return {item.detector_name: item.detector_version for item in self._detectors}

    def detect(self, context: DetectorContext) -> DetectorResult:
        combined = DetectorResult()
        self.last_metrics = []
        for detector in self._detectors:
            started = perf_counter(); supported = detector.supports(context)
            if not supported:
                self.last_metrics.append(DetectorRunMetric(detector=detector.detector_name, version=detector.detector_version, supported=False, duration_ms=(perf_counter() - started) * 1000, evidence_count=0, node_count=0))
                continue
            try:
                result = detector.detect(context)
            except Exception as exc:
                self.last_metrics.append(DetectorRunMetric(detector=detector.detector_name, version=detector.detector_version, supported=True, duration_ms=(perf_counter() - started) * 1000, evidence_count=0, node_count=0, error=str(exc)))
                continue
            self.last_metrics.append(DetectorRunMetric(detector=detector.detector_name, version=detector.detector_version, supported=True, duration_ms=(perf_counter() - started) * 1000, evidence_count=len(result.evidence), node_count=len(result.nodes)))
            combined.evidence.extend(result.evidence); combined.capabilities.extend(result.capabilities)
            combined.nodes.extend(result.nodes); combined.edges.extend(result.edges)
        return combined
