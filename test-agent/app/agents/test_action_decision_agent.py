from __future__ import annotations

from app.agents.base_agent import BaseAgent, log_exception, log_performance
from app.prompts.test_action_prompt import build_test_action_prompt
from app.schemas.decision_trace import DecisionTrace
from app.schemas.behavioral_test_unit import BehavioralTestUnit
from app.schemas.spec_placement import SpecPlacementDecision
from app.schemas.test_action_decision import TestActionDecision


class TestActionDecisionAgent(BaseAgent):
    agent_name = "test_action_decision_agent"

    @log_performance("test_action_decision_agent.decide")
    def decide(
        self,
        placement: SpecPlacementDecision,
        ranked_tests: list[BehavioralTestUnit],
    ) -> TestActionDecision:
        context = self.log_start("test_action")
        try:
            return self.complete_structured(
                prompt=build_test_action_prompt(placement, ranked_tests),
                response_model=TestActionDecision,
            )
        except Exception as exc:
            log_exception(exc, context=context)
            raise

    def _fallback_decision(
        self,
        placement: SpecPlacementDecision,
        ranked_tests: list[BehavioralTestUnit],
    ) -> TestActionDecision:
        if placement.create_new:
            action = "create_new_spec"
            target_test_title = None
        elif ranked_tests:
            action = "extend_existing_test"
            target_test_title = ranked_tests[0].test_title
        else:
            action = "append_new_test"
            target_test_title = None
        return TestActionDecision(
            action=action,
            target_test_title=target_test_title,
            confidence=0.35,
            decision_trace=DecisionTrace(
                decision=action,
                confidence=0.35,
                justification="Deterministic fallback used because no LLM decision was available.",
                evidence=["Placement decision and ranked test candidates"],
                risk="medium",
                fallback="Prefer append/create when extension ownership is unclear",
            ),
        )
