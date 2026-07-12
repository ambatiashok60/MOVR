from __future__ import annotations



from worktop.test_agent.app.agents.candidate_test_ranking_agent import CandidateTestRankingAgent
from worktop.test_agent.app.agents.test_action_decision_agent import TestActionDecisionAgent
from worktop.test_agent.app.llm.llm_client import LLMClient
from worktop.test_agent.app.schemas.behavioral_test_unit import BehavioralTestUnit
from worktop.test_agent.app.schemas.functional_intent import FunctionalIntent
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.spec_placement import SpecPlacementDecision
from worktop.test_agent.app.schemas.test_action_decision import TestActionDecision
from worktop.core_services.app.utility.custom_logger.logging import logger



class TestActionService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.ranking_agent = CandidateTestRankingAgent(llm_client=llm_client)
        self.decision_agent = TestActionDecisionAgent(llm_client=llm_client)

    def decide(
        self,
        placement: SpecPlacementDecision,
        candidates: list[BehavioralTestUnit],
        intent: FunctionalIntent | None = None,
        ui_context: PlaywrightUiContext | None = None,
        repo_path: str | None = None,
    ) -> TestActionDecision:
        logger.info(
            "[playwright-generation] stage=test_action status=started target_spec=%s candidates=%s",
            placement.target_spec_file,
            len(candidates),
        )
        try:
            ranked = self.ranking_agent.rank(candidates, intent)
            decision = self.decision_agent.decide(placement, ranked, ui_context, repo_path)
            logger.info(
                "[playwright-generation] stage=test_action status=completed action=%s target_test=%s",
                decision.action,
                decision.target_test_title or "none",
            )
            logger.info(
                "[playwright-generation] stage=test_action decision=%s evidence=%s risk=%s fallback=%s",
                decision.decision_trace.decision,
                decision.decision_trace.evidence,
                decision.decision_trace.risk,
                decision.decision_trace.fallback,
            )
            return decision
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=test_action status=failed_using_fallback error=%s",
                exc,
            )
            ranked = self.ranking_agent.rank(candidates, intent)
            decision = self.decision_agent._fallback_decision(placement, ranked)
            logger.info(
                "[playwright-generation] stage=test_action status=fallback_completed action=%s",
                decision.action,
            )
            logger.info(
                "[playwright-generation] stage=test_action fallback_reason=%s evidence=%s",
                decision.decision_trace.justification,
                decision.decision_trace.evidence,
            )
            return decision
