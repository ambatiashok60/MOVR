from __future__ import annotations
from app.ai_workspace.domain.agent_turn import AgentTurn
from app.ai_workspace.application.agent.patch_validation_service import PatchValidationResult

class EngineeringReviewService:
    """Evidence-based score; no model self-scoring is accepted."""
    def build(self, turn: AgentTurn, validation: PatchValidationResult, observation_count: int) -> dict:
        correctness = 25 if validation.passed and turn.root_cause else 10
        repository_fit = min(15, len(turn.evidence) * 3 + min(observation_count, 3) * 2)
        architecture = 10 if turn.plan.get("steps") else 5
        safety = 15 if validation.passed and not any(c.status == "deleted" for c in turn.file_changes) else 8
        validation_score = 15 if validation.passed else 0
        maintainability = 10 if 0 < len(turn.file_changes) <= 5 else 5
        operational = 5 if turn.final_summary or turn.reasoning_summary else 2
        score = correctness + repository_fit + architecture + safety + validation_score + maintainability + operational
        risk = "high" if any(c.status == "deleted" for c in turn.file_changes) else "medium" if len(turn.file_changes) > 5 else "low"
        findings = list(validation.findings)
        if len(turn.evidence) < 2:
            findings.append("Limited repository evidence; review root-cause confidence.")
        return {
            "quality_score": score,
            "risk_level": risk,
            "confidence": round(min(0.95, 0.45 + len(turn.evidence) * 0.1 + min(observation_count, 4) * 0.05), 2),
            "root_cause": turn.root_cause,
            "evidence": turn.evidence,
            "validation": ["Deterministic staged-content validation passed"] if validation.passed else validation.findings,
            "remaining_risks": findings,
            "approval_required": risk == "high",
        }
