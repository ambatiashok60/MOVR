from __future__ import annotations

from app.prompts.prompt_sections import as_json, response_contract
from app.schemas.behavioral_test_unit import BehavioralTestUnit
from app.schemas.playwright_ui_context import PlaywrightUiContext
from app.schemas.spec_placement import SpecPlacementDecision
from app.schemas.test_action_decision import TestActionDecision


def build_test_action_prompt(
    placement: SpecPlacementDecision,
    ranked_tests: list[BehavioralTestUnit],
    ui_context: PlaywrightUiContext | None = None,
) -> str:
    return f"""
You are deciding whether to extend, append, or create Playwright coverage.

Rules:
- Same flow plus missing coverage means extend existing test.
- Same module but different scenario means append a new test.
- Different owner means create a new spec.
- Preserve proven execution flow; do not randomly insert lines.
- Reuse existing auth/session, fixture, mock/stub, and page-object patterns.
- Avoid duplicate coverage when an existing spec already proves the same visible behavior.

Spec placement:
{as_json(placement)}

Ranked candidate tests:
{as_json(ranked_tests)}

Playwright UI context:
{as_json(ui_context or {})}

{response_contract(TestActionDecision)}
"""
