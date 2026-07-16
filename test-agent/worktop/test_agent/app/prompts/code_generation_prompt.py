from __future__ import annotations

from worktop.test_agent.app.prompts.prompt_sections import (
    as_json,
    curated_ui_context,
    playwright_best_practices,
    response_contract,
)
from worktop.test_agent.app.schemas.behavioral_test_unit import AnchorFlowContext, ExistingTestContext
from worktop.test_agent.app.schemas.code_patch import PatchSet
from worktop.test_agent.app.schemas.flow_merge import FlowMergePlan
from worktop.test_agent.app.schemas.locator_decision import LocatorDecision
from worktop.test_agent.app.schemas.ownership_resolution import OwnershipResolution
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.spec_placement import SpecPlacementDecision
from worktop.test_agent.app.schemas.test_action_decision import TestActionDecision


def build_code_generation_prompt(
    placement: SpecPlacementDecision,
    action: TestActionDecision,
    ui_context: PlaywrightUiContext | None = None,
    existing_test_context: ExistingTestContext | None = None,
    flow_plan: FlowMergePlan | None = None,
    ownership: OwnershipResolution | None = None,
    anchor_flow_context: AnchorFlowContext | None = None,
    locator_decisions: list[LocatorDecision] | None = None,
    include_contract: bool = True,
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
- Use create/replace_test/append_test for specs. For supporting TypeScript files, use insert_class_member, insert_object_property, or insert_import with target_symbol and member_name instead of appending at EOF.
- Emit exactly one primary spec patch plus only the supporting page-object, locator, import, fixture, or utility patches required by that test.
- Never append a class method, object property, or import as raw file-ending text.
- Generate CI-safe Playwright UI tests, not backend/API integration tests.
- Reuse detected mocks/stubs, fixtures, auth/session setup, test data builders, and page objects.
- Ground locators in UI source evidence or existing page object methods.
- Prefer getByRole, getByLabel, getByPlaceholder, existing page objects, then getByTestId when that is the repo convention.
- Do not use fixed sleeps, arbitrary timeouts, or brittle CSS/XPath unless the repository already requires them.
- Include meaningful user-visible assertions that prove the requested behavior.
- Include error, empty, loading, role, or permission assertions only when they are part of the requested functional intent or nearby repo pattern.
- Keep generated tests parallel-safe and deterministic under CI.
- If Test action is extend_existing_test, use the Existing test context below as the only target test.
- For extend_existing_test, emit replace_test with the Existing test context file_path, target_test_title, target_describe_title, and expected_source. Do not use line-based replace.
- For extend_existing_test, patch content must be the full replacement test block, not a fragment.
- For extend_existing_test, preserve the existing test title, fixtures, page objects, mocks, setup, and proven flow unless the requested behavior requires a minimal change.
- Do not extend any other test block or overwrite the whole spec file.
- When a Flow merge plan is provided, keep its stable_region and preserved_steps intact and only add its extension_region and added_steps.
- When an Ownership resolution is provided, place new locators, helpers, and methods in the resolved owner (owner_path/owner_kind); only inline them in the spec when the owner_kind is spec.
- If Test action is append_new_test and an Anchor flow context is provided, copy that sibling test's setup, auth/session, navigation, fixtures, and page-object calls verbatim as one uninterrupted base-flow block.
- Treat the Anchor flow context behavior_summary and source_excerpt as the proven partial flow. Preserve its required setup and steps, then add only the requested new branch and assertions.
- Do not omit, reorder, rewrite, or insert new steps between statements copied from the anchor flow. Add the new scenario steps only after the preserved base-flow block reaches the required state.
- In the new test, add `// Anchor flow: <anchor test title>` immediately before the copied anchor statements and `// End anchor flow; new scenario steps begin below.` immediately after them. These comments document which test was reused and the exact extent of reuse.
- For append_new_test, add only the steps and assertions the requested behavior needs on top of the anchor flow; do not reinvent a parallel setup or drop the anchor's proven setup.
- For append_new_test, never edit or replace the original anchor test. The new test may copy its proven inner flow, but must use a unique title and add the requested behavior afterward.
- For append_new_test, emit append_test with one complete test block and target_describe_title. Do not provide a line-based insertion position; the writer resolves the describe's current structural closing offset immediately before writing.
- The generated test title must be unique within the target file.
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
{as_json(curated_ui_context(ui_context))}

{response_contract(PatchSet) if include_contract else ''}
"""
