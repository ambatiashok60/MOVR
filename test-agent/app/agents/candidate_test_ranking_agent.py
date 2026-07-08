from __future__ import annotations

from app.agents.base_agent import BaseAgent, log_exception, log_metric, log_performance
from app.schemas.behavioral_test_unit import BehavioralTestUnit


class CandidateTestRankingAgent(BaseAgent):
    agent_name = "candidate_test_ranking_agent"

    @log_performance("candidate_test_ranking_agent.rank")
    def rank(self, candidate_tests: list[BehavioralTestUnit]) -> list[BehavioralTestUnit]:
        context = self.log_start("candidate_ranking")
        try:
            log_metric("candidate_tests_count", len(candidate_tests))
            return candidate_tests
        except Exception as exc:
            log_exception(exc, context=context)
            raise
