from __future__ import annotations

from pathlib import Path

from worktop.api_agent.app.autonomy.evidence_catalog import EvidenceCatalog
from worktop.api_agent.app.autonomy.targeted_discovery_service import TargetedDiscoveryService
from worktop.api_agent.app.schemas.autonomy import (
    CapabilityAssessment,
    PhaseTransition,
    ReadinessStatus,
)
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.services.capability_assessment_service import CapabilityAssessmentService


class AutonomousDiscoveryWorkflowController:
    """Evidence-driven discovery loop used in shadow mode before strategy composition."""

    def __init__(self, assessment_service: CapabilityAssessmentService | None = None, discovery_service: TargetedDiscoveryService | None = None, max_rounds: int = 2) -> None:
        self.assessment_service = assessment_service or CapabilityAssessmentService()
        self.discovery_service = discovery_service or TargetedDiscoveryService()
        self.catalog = EvidenceCatalog()
        self.max_rounds = max_rounds

    def run(self, profile: RepoProfile) -> CapabilityAssessment:
        assessment = self.assessment_service.assess(profile)
        if assessment.readiness.status != ReadinessStatus.NEEDS_MORE_EVIDENCE:
            return assessment
        root = Path(profile.repo_path)
        previous_signature: tuple[str, ...] | None = None
        for round_index in range(1, self.max_rounds + 1):
            requests = assessment.readiness.requested_discovery
            if not requests:
                assessment.stopped_reason = "No targeted discovery request was available."
                break
            signature = tuple(sorted(f"{item.target_capability}:{','.join(item.search_symbols)}" for item in requests))
            if signature == previous_signature:
                assessment.stopped_reason = "Targeted discovery would repeat the previous request without new evidence."
                assessment.readiness.status = ReadinessStatus.NEEDS_REVIEW
                assessment.readiness.recommended_next_stage = None
                assessment.readiness.review_reasons.append("Repeated targeted discovery could not resolve a repository-native testing mechanism.")
                break
            previous_signature = signature
            revision = assessment.graph.repository_revision if assessment.graph else "unknown"
            evidence, capabilities, nodes, edges = self.discovery_service.discover(root, revision, requests)
            assessment.transitions.append(PhaseTransition(from_stage="capability_assessment", to_stage="targeted_discovery", outcome=ReadinessStatus.NEEDS_MORE_EVIDENCE, reason=requests[0].reason, evidence_ids=assessment.readiness.evidence_ids))
            assessment.discovery_rounds = round_index
            if assessment.telemetry:
                assessment.telemetry.discovery_rounds = round_index
            if not evidence:
                assessment.transitions.append(PhaseTransition(from_stage="targeted_discovery", to_stage=None, outcome=ReadinessStatus.NEEDS_REVIEW, reason="Targeted discovery found no new evidence."))
                assessment.readiness.status = ReadinessStatus.NEEDS_REVIEW
                assessment.readiness.recommended_next_stage = None
                assessment.readiness.review_reasons.append("No repository-native test mechanism was found after targeted source and test discovery.")
                assessment.stopped_reason = "No new evidence was found."
                break
            versions = assessment.graph.detector_versions if assessment.graph else {}
            all_evidence, all_capabilities, graph = self.catalog.merge(revision, versions, [*assessment.evidence, *evidence], [*assessment.capabilities, *capabilities], [*(assessment.graph.nodes if assessment.graph else []), *nodes], [*(assessment.graph.edges if assessment.graph else []), *edges])
            assessment.evidence = all_evidence; assessment.capabilities = all_capabilities; assessment.graph = graph
            assessment = self.assessment_service.reassess(profile, assessment)
            assessment.discovery_rounds = round_index
            assessment.transitions.append(PhaseTransition(from_stage="targeted_discovery", to_stage=assessment.readiness.recommended_next_stage, outcome=assessment.readiness.status, reason=(assessment.readiness.review_reasons or assessment.readiness.unresolved_questions or ["Targeted discovery resolved readiness."])[0], evidence_ids=[item.evidence_id for item in evidence]))
            if assessment.readiness.status != ReadinessStatus.NEEDS_MORE_EVIDENCE:
                break
        return assessment
