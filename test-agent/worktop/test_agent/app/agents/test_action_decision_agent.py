from __future__ import annotations

from worktop.test_agent.app.agents.base_agent import BaseAgent, logger
from worktop.test_agent.app.prompts.test_action_prompt import build_test_action_prompt
from worktop.test_agent.app.schemas.decision_trace import DecisionTrace
from worktop.test_agent.app.schemas.exploration import TestActionTurn
from worktop.test_agent.app.schemas.behavioral_test_unit import BehavioralTestUnit
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.spec_placement import SpecPlacementDecision
from worktop.test_agent.app.schemas.test_action_decision import TestActionDecision, TestActions


class TestActionDecisionAgent(BaseAgent):
    agent_name = "test_action_decision_agent"

    def decide(
        self,
        placement: SpecPlacementDecision,
        ranked_tests: list[BehavioralTestUnit],
        ui_context: PlaywrightUiContext | None = None,
        repo_path: str | None = None,
    ) -> TestActionDecision:
        context = self.log_start("test_action")
        try:
            prompt = build_test_action_prompt(
                placement, ranked_tests, ui_context, include_contract=False
            )
            prompt += (
                "\n\nBefore deciding extend vs append vs create, READ the actual "
                "candidate test blocks (and the target spec) so the decision is "
                "based on real coverage, not excerpts. State your reasoning each "
                "turn and a reason for every file you request."
            )
            return self.complete_with_exploration(
                prompt, TestActionTurn, repo_path or "."
            )
        except Exception as exc:
            logger.exception(
                "[playwright-generation] agent=%s stage=test_action status=failed context=%s error=%s",
                self.agent_name,
                context,
                exc,
            )
            raise

    def _fallback_decision(
        self,
        placement: SpecPlacementDecision,
        ranked_tests: list[BehavioralTestUnit],
    ) -> TestActionDecision:
        if placement.create_new:
            action = TestActions.CREATE_NEW_SPEC
            target_test_title = None
        elif ranked_tests:
            action = TestActions.EXTEND_EXISTING_TEST
            target_test_title = ranked_tests[0].test_title
        else:
            action = TestActions.APPEND_NEW_TEST
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
