from __future__ import annotations

from app.prompts.prompt_sections import (
    as_json,
    playwright_best_practices,
    response_contract,
)
from app.schemas.behavioral_test_unit import AnchorFlowContext, ExistingTestContext
from app.schemas.code_patch import PatchSet
from app.schemas.flow_merge import FlowMergePlan
from app.schemas.locator_decision import LocatorDecision
from app.schemas.ownership_resolution import OwnershipResolution
from app.schemas.playwright_ui_context import PlaywrightUiContext
from app.schemas.spec_placement import SpecPlacementDecision
from app.schemas.test_action_decision import TestActionDecision


def build_code_generation_prompt(
    placement: SpecPlacementDecision,
    action: TestActionDecision,
    ui_context: PlaywrightUiContext | None = None,
    existing_test_context: ExistingTestContext | None = None,
    flow_plan: FlowMergePlan | None = None,
    ownership: OwnershipResolution | None = None,
    anchor_flow_context: AnchorFlowContext | None = None,
    locator_decisions: list[LocatorDecision] | None = None,
) -> str:
    best_practices_section = (
        f"\n{playwright_best_practices()}\n" if action.action == "create_new_spec" else ""
    )
    return f"""
You are generating structured Playwright patch intent.

Rules:
- Return structured patches only.
- Do not overwrite whole specs for an extension.
- Do not add raw locators to specs when page objects exist.
- Use create, replace, or append operations only.
- Generate CI-safe Playwright UI tests, not backend/API integration tests.
- Reuse detected mocks/stubs, fixtures, auth/session setup, test data builders, and page objects.
- Ground locators in UI source evidence or existing page object methods.
- Prefer getByRole, getByLabel, getByPlaceholder, existing page objects, then getByTestId when that is the repo convention.
- Do not use fixed sleeps, arbitrary timeouts, or brittle CSS/XPath unless the repository already requires them.
- Include meaningful user-visible assertions that prove the requested behavior.
- Include error, empty, loading, role, or permission assertions only when they are part of the requested functional intent or nearby repo pattern.
- Keep generated tests parallel-safe and deterministic under CI.
- If Test action is extend_existing_test, use the Existing test context below as the only target test.
- For extend_existing_test, emit a replace patch for the exact Existing test context file_path, start_line, and end_line.
- For extend_existing_test, patch content must be the full replacement test block, not a fragment.
- For extend_existing_test, preserve the existing test title, fixtures, page objects, mocks, setup, and proven flow unless the requested behavior requires a minimal change.
- Do not extend any other test block or overwrite the whole spec file.
- When a Flow merge plan is provided, keep its stable_region and preserved_steps intact and only add its extension_region and added_steps.
- When an Ownership resolution is provided, place new locators, helpers, and methods in the resolved owner (owner_path/owner_kind); only inline them in the spec when the owner_kind is spec.
- If Test action is append_new_test and an Anchor flow context is provided, reuse that sibling test's setup, auth/session, navigation, fixtures, and page objects verbatim as the base of the new test.
- For append_new_test, add only the steps and assertions the requested behavior needs on top of the anchor flow; do not reinvent a parallel setup or drop the anchor's proven setup.
- For append_new_test, the anchor is a reference only: never edit, replace, or duplicate the anchor test itself.
- If Test action is create_new_spec and an Anchor flow context is provided, mirror its setup, auth/session, fixture, and page-object style in the new spec; do not copy its test titles or assertions.
- When Locator decisions are provided, use exactly those locators for the matching interactions; do not substitute or invent alternatives that lack source evidence.
- Never call a page-object method, helper, or fixture that does not already exist in the repository or in a patch you are emitting in this same patch set.
- Every relative import you emit must resolve to an existing repository file or to a file created by a patch in this same patch set.
{best_practices_section}
Spec placement:
{as_json(placement)}

Test action:
{as_json(action)}

Existing test context:
{as_json(existing_test_context or {})}

Anchor flow context:
{as_json(anchor_flow_context or {})}

Flow merge plan:
{as_json(flow_plan or {})}

Ownership resolution:
{as_json(ownership or {})}

Locator decisions (evidence-grounded, use these exact locators):
{as_json([decision.model_dump() for decision in (locator_decisions or [])])}

Playwright UI context:
{as_json(ui_context or {})}

{response_contract(PatchSet)}
"""
