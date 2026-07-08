from __future__ import annotations

from typing import Any

from worktop.core_services.app.utility.custom_logger.log_helpers import (
    log_card_simple,
    log_exception,
    log_metric,
    log_step,
)
from worktop.core_services.app.utility.custom_logger.logging import (
    log_performance,
    logger,
)

from app.agents.candidate_test_ranking_agent import CandidateTestRankingAgent
from app.agents.test_action_decision_agent import TestActionDecisionAgent
from app.llm.llm_client import LLMClient
from app.schemas.behavioral_test_unit import BehavioralTestUnit
from app.schemas.playwright_ui_context import PlaywrightUiContext
from app.schemas.spec_placement import SpecPlacementDecision
from app.schemas.test_action_decision import TestActionDecision


class TestActionService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.ranking_agent = CandidateTestRankingAgent()
        self.decision_agent = TestActionDecisionAgent(llm_client=llm_client)

    @log_performance("test_action_service.decide")
    def decide(
        self,
        placement: SpecPlacementDecision,
        candidates: list[BehavioralTestUnit],
        ui_context: PlaywrightUiContext | None = None,
    ) -> TestActionDecision:
        log_step("test_action_service_started", {"target_spec_file": placement.target_spec_file})
        try:
            ranked = self.ranking_agent.rank(candidates)
            return self.decision_agent.decide(placement, ranked, ui_context)
        except Exception as exc:
            log_exception(exc, context={"stage": "test_action"})
            raise
