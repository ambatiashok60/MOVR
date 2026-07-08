from __future__ import annotations

from app.prompts.prompt_sections import as_json, response_contract
from app.schemas.playwright_ui_context import PlaywrightUiContext
from app.schemas.spec_placement import SpecPlacementDecision
from app.schemas.test_action_decision import TestActionDecision


def build_code_generation_prompt(
    placement: SpecPlacementDecision,
    action: TestActionDecision,
    ui_context: PlaywrightUiContext | None = None,
) -> str:
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

Spec placement:
{as_json(placement)}

Test action:
{as_json(action)}

Playwright UI context:
{as_json(ui_context or {})}

{response_contract("PatchSet")}
"""
