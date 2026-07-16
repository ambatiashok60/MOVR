from __future__ import annotations

from worktop.api_agent.app.agents.strategy_reasoning_agent import StrategyReasoningAgent
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.strategy_reasoning import StrategyReasoningOutput
from worktop.api_agent.app.utils.logging_utils import log_exception, log_step


class StrategyReasoningService:
    """Applies a structured LLM review without allowing it to bypass compatibility."""

    def review(self, profile: RepoProfile, agent: StrategyReasoningAgent) -> StrategyReasoningOutput | None:
        plan = profile.generation_plan
        assessment = profile.capability_assessment
        if plan is None or assessment is None:
            return None
        try:
            output = agent.review(profile)
        except Exception as exc:
            log_exception(exc, context={"stage": "strategy_reasoning_review"})
            plan.review_reasons.append("Structured strategy reasoning was unavailable; deterministic capability plan retained.")
            return None
        allowed = {item.strategy_name for item in plan.candidates}
        known_evidence = {item.evidence_id for item in assessment.evidence}
        if output.selected_strategy and output.selected_strategy not in allowed:
            plan.review_reasons.append(f"Model proposed incompatible/unregistered strategy `{output.selected_strategy}`; deterministic selection retained.")
            output.decision = "needs_review"; output.selected_strategy = plan.selected_strategy; output.recommended_next_stage = "review"
        unknown = sorted(set(output.evidence_ids) - known_evidence)
        if unknown:
            plan.review_reasons.append("Model cited unknown evidence IDs; deterministic evidence remains authoritative.")
            output.evidence_ids = [item for item in output.evidence_ids if item in known_evidence]
            output.decision = "needs_review"; output.recommended_next_stage = "review"
        if output.selected_strategy and output.selected_strategy != plan.selected_strategy:
            candidate = next((item for item in plan.candidates if item.strategy_name == output.selected_strategy and item.compatible), None)
            if candidate is None:
                output.selected_strategy = plan.selected_strategy
            else:
                plan.selected_strategy = candidate.strategy_name; plan.confidence = min(candidate.confidence, output.confidence)
        if output.decision != "confirm":
            plan.status = "needs_review"
            plan.review_reasons.extend(output.reasons)
            plan.review_reasons.extend(output.unresolved_questions)
        log_step("strategy_reasoning_review_completed", {"decision": output.decision, "selected_strategy": output.selected_strategy, "evidence_count": len(output.evidence_ids)})
        return output
