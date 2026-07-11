from __future__ import annotations

from worktop.test_agent.app.prompts.prompt_sections import as_json, response_contract
from worktop.test_agent.app.schemas.code_patch import PatchSet
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.validation_result import ValidationResult


def build_repair_prompt(patches: PatchSet, validation: ValidationResult) -> str:
    return f"""
You are repairing generated Playwright patches after validation failure.

Rules:
- Fix only generated patch scope.
- Do not modify unrelated repository files.
- Return structured patches only.

Current patches:
{as_json(patches)}

Validation result:
{as_json(validation)}

{response_contract(PatchSet)}
"""


def build_critic_prompt(
    patches: PatchSet,
    ui_context: PlaywrightUiContext | None = None,
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

Patches:
{as_json(patches)}

Playwright UI context:
{as_json(ui_context or {})}

{response_contract(PatchSet)}
"""
