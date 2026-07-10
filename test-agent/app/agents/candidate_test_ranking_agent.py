from __future__ import annotations

from app.agents.base_agent import BaseAgent, logger
from app.prompts.candidate_ranking_prompt import build_candidate_ranking_prompt
from app.schemas.behavioral_test_unit import BehavioralTestUnit
from app.schemas.candidate_ranking import CandidateRanking
from app.schemas.functional_intent import FunctionalIntent


class CandidateTestRankingAgent(BaseAgent):
    agent_name = "candidate_test_ranking_agent"

    def rank(
        self,
        candidate_tests: list[BehavioralTestUnit],
        intent: FunctionalIntent | None = None,
    ) -> list[BehavioralTestUnit]:
        context = self.log_start("candidate_ranking")
        logger.info(
            "[playwright-generation] agent=%s stage=candidate_ranking candidate_tests=%s",
            self.agent_name,
            len(candidate_tests),
        )
        if len(candidate_tests) <= 1 or intent is None or self.llm is None:
            logger.info(
                "[playwright-generation] agent=%s stage=candidate_ranking "
                "status=passthrough reason=%s",
                self.agent_name,
                "insufficient_candidates_or_context",
            )
            return candidate_tests
        try:
            ranking = self.complete_structured(
                prompt=build_candidate_ranking_prompt(intent, candidate_tests),
                response_model=CandidateRanking,
            )
            ordered = self._apply_ranking(candidate_tests, ranking)
            logger.info(
                "[playwright-generation] agent=%s stage=candidate_ranking status=completed "
                "ranked=%s top=%s",
                self.agent_name,
                len(ordered),
                ordered[0].test_title if ordered else "none",
            )
            return ordered
        except Exception as exc:
            logger.exception(
                "[playwright-generation] agent=%s stage=candidate_ranking "
                "status=failed_using_passthrough context=%s error=%s",
                self.agent_name,
                context,
                exc,
            )
            return candidate_tests

    def _apply_ranking(
        self,
        candidate_tests: list[BehavioralTestUnit],
        ranking: CandidateRanking,
    ) -> list[BehavioralTestUnit]:
        remaining = list(candidate_tests)
        ordered: list[BehavioralTestUnit] = []
        for ref in ranking.ranked:
            match = self._match(remaining, ref)
            if match is not None:
                remaining.remove(match)
                ordered.append(match)
        # Preserve any candidates the model failed to reference, in original order.
        ordered.extend(remaining)
        return ordered

    def _match(
        self,
        candidates: list[BehavioralTestUnit],
        ref: object,
    ) -> BehavioralTestUnit | None:
        file_path = getattr(ref, "file_path", None)
        test_title = getattr(ref, "test_title", None)
        start_line = getattr(ref, "start_line", None)
        exact = [
            candidate
            for candidate in candidates
            if candidate.file_path == file_path
            and candidate.test_title == test_title
            and (start_line is None or candidate.start_line == start_line)
        ]
        if exact:
            return exact[0]
        loose = [
            candidate
            for candidate in candidates
            if candidate.file_path == file_path and candidate.test_title == test_title
        ]
        return loose[0] if loose else None
