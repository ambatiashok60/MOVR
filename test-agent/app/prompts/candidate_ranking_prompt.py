from __future__ import annotations

from app.prompts.prompt_sections import as_json, response_contract
from app.schemas.behavioral_test_unit import BehavioralTestUnit
from app.schemas.candidate_ranking import CandidateRanking
from app.schemas.functional_intent import FunctionalIntent


def build_candidate_ranking_prompt(
    intent: FunctionalIntent,
    candidates: list[BehavioralTestUnit],
) -> str:
    return f"""
You are ranking existing Playwright tests by how well each one already owns the
behavior described by the functional intent.

Rules:
- Rank higher when a candidate covers the same route, screen, actor journey, or assertions.
- Rank higher when a candidate shares fixtures, page objects, auth/session, or mock setup with the intent.
- Rank lower when a candidate proves unrelated behavior even if it lives nearby.
- Return every candidate exactly once, most relevant first.
- Identify each candidate by its file_path, test_title, and start_line so it can be matched back.
- Set relevance between 0 and 1 and give a short reason grounded in shared behavior.

Functional intent:
{as_json(intent)}

Candidate tests:
{as_json([candidate.model_dump() for candidate in candidates])}

{response_contract(CandidateRanking)}
"""
