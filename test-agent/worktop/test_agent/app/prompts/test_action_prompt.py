from __future__ import annotations

from worktop.test_agent.app.prompts.prompt_sections import (
    as_json,
    curated_test_units,
    curated_ui_context,
    response_contract,
)
from worktop.test_agent.app.schemas.behavioral_test_unit import BehavioralTestUnit
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.spec_placement import SpecPlacementDecision
from worktop.test_agent.app.schemas.test_action_decision import TestActionDecision


def build_test_action_prompt(
    placement: SpecPlacementDecision,
    ranked_tests: list[BehavioralTestUnit],
    ui_context: PlaywrightUiContext | None = None,
    include_contract: bool = True,
) -> str:
    return f"""
You are deciding whether to extend, append, or create Playwright coverage.

Rules:
- Prefer extending an existing test when the request continues the same user journey, setup, state transition, and expected outcome, provided every proven existing step and assertion can be preserved.
- Append only when the request is a genuinely separate scenario, branch, role, data condition, or outcome that should run and report independently.
- Do not append merely because an extension requires careful parsing or patch placement; those are repairable implementation issues.
- Avoid suite bloat: if a new test would mostly duplicate an existing test's flow, extend the existing test instead.
- Different owner means create a new spec.
- Preserve proven execution flow; do not randomly insert lines.
- Reuse existing auth/session, fixture, mock/stub, and page-object patterns.
- Avoid duplicate coverage when an existing spec already proves the same visible behavior.
- Choose extend_existing_test only after reading the exact candidate block and confirming its title and source range. Include that evidence in the decision trace.
- For extend_existing_test, always return target_test_title, target_file_path, and target_start_line copied exactly from the selected candidate. These fields are the stable handoff to patch generation.

Spec placement:
{as_json(placement)}

Ranked candidate tests:
{as_json(curated_test_units(ranked_tests))}

Playwright UI context:
{as_json(curated_ui_context(ui_context))}

{response_contract(TestActionDecision) if include_contract else ''}
"""
