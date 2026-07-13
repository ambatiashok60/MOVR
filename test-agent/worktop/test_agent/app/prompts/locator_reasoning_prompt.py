from __future__ import annotations

from worktop.test_agent.app.prompts.prompt_sections import as_json, response_contract
from worktop.test_agent.app.schemas.locator_decision import LocatorDecisionSet
from worktop.test_agent.app.schemas.source_intelligence import SourceIntelligence
from worktop.test_agent.app.schemas.behavioral_test_unit import AnchorFlowContext
from worktop.test_agent.app.schemas.functional_intent import FunctionalIntent
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.test_action_decision import TestActionDecision
from worktop.test_agent.app.prompts.prompt_sections import curated_ui_context


def build_locator_reasoning_prompt(
    source: SourceIntelligence,
    action: TestActionDecision | None = None,
    anchor: AnchorFlowContext | None = None,
    intent: FunctionalIntent | None = None,
    ui_context: PlaywrightUiContext | None = None,
) -> str:
    return f"""
You are choosing Playwright locators from source evidence.

Rules:
- Do not invent selectors without source evidence.
- Preserve locators and page-object calls from the anchor flow exactly; do not create decisions for its existing steps.
- For append_new_test, return decisions only for new interactions required by the intent beyond the anchor's behavior_summary and source_excerpt.
- Prefer an existing page-object method, then accessible locators, then stable testing attributes.
- Use broad UI context as supporting evidence, but do not let unrelated repository patterns override the target anchor flow.
- Explain alternatives rejected and confidence.

Test action:
{as_json(action or {})}

Functional intent:
{as_json(intent or {})}

Selected anchor flow:
{as_json(anchor or {})}

Source intelligence:
{as_json(source)}

Repository UI context:
{as_json(curated_ui_context(ui_context))}

{response_contract(LocatorDecisionSet)}
"""
