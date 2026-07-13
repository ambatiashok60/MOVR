from __future__ import annotations

from worktop.test_agent.app.prompts.prompt_sections import as_json, response_contract
from worktop.test_agent.app.schemas.code_patch import PatchSet
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.validation_result import ValidationResult
from worktop.test_agent.app.schemas.behavioral_test_unit import AnchorFlowContext
from worktop.test_agent.app.schemas.locator_decision import LocatorDecision


def build_repair_prompt(
    patches: PatchSet,
    validation: ValidationResult,
    anchor: AnchorFlowContext | None = None,
    locator_decisions: list[LocatorDecision] | None = None,
) -> str:
    return f"""
You are repairing generated Playwright patches after validation failure.

Rules:
- Fix only generated patch scope.
- Do not modify unrelated repository files.
- Return structured patches only.
- Repair parser, line-range, describe-placement, duplicate-title, and anchor-boundary failures in the patch instead of changing the intended scenario.
- When validation reports a duplicate test title, rename only the generated test to a concise behavior-specific title that is absent from the target spec. Preserve its body, operation, path, and structural target.
- For extension repairs, preserve every existing step and assertion and keep the exact parser-validated target range.
- For append repairs, preserve append_test and target_describe_title, keep the selected anchor flow uninterrupted, retain its boundary comments, and return exactly one complete test block.
- For supporting page or utility patches, preserve insert_class_member, insert_object_property, or insert_import plus target_symbol/member_name so the writer can re-resolve the current structural insertion point.

Current patches:
{as_json(patches)}

Validation result:
{as_json(validation)}

Selected anchor flow and insertion context:
{as_json(anchor or {})}

Locator decisions for new steps after the anchor flow:
{as_json(locator_decisions or [])}

{response_contract(PatchSet)}
"""


def build_critic_prompt(
    patches: PatchSet,
    ui_context: PlaywrightUiContext | None = None,
    anchor: AnchorFlowContext | None = None,
    locator_decisions: list[LocatorDecision] | None = None,
) -> str:
    return f"""
You are reviewing generated Playwright UI patches for CI quality.

Rules:
- Keep only safe, scoped, maintainable patch intent.
- Preserve structured patch format.
- Do not add provider-specific SDK usage.
- Reject shallow assertions that do not prove user-visible behavior.
- Reject fixed sleeps, arbitrary timeout waits, and invented selectors.
- Ensure mocks/stubs, auth/session setup, fixtures, and page objects follow existing repo patterns when present.
- Ensure generated tests are deterministic, parallel-safe, and useful in CI reports.
- When an anchor is supplied, preserve its copied inner flow and anchor boundary comments exactly.
- Apply locator decisions only to the new steps after the anchor boundary; never rewrite proven anchor locators.

Patches:
{as_json(patches)}

Playwright UI context:
{as_json(ui_context or {})}

Selected anchor flow and insertion context:
{as_json(anchor or {})}

Locator decisions for new steps after the anchor flow:
{as_json(locator_decisions or [])}

{response_contract(PatchSet)}
"""
