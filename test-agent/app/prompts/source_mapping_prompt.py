from __future__ import annotations

from app.prompts.prompt_sections import as_json, response_contract
from app.schemas.functional_intent import FunctionalIntent
from app.schemas.playwright_ui_context import PlaywrightUiContext


def build_source_mapping_prompt(
    intent: FunctionalIntent,
    ui_context: PlaywrightUiContext | None = None,
) -> str:
    return f"""
You are mapping functional intent to source evidence.

Rules:
- Identify routes, components, services, and locator evidence.
- Evidence must be grounded in repository source when available.
- Leave sections empty when there is no evidence.
- Prefer UI source, existing Playwright specs, page objects, fixtures, and mocks.

Functional intent:
{as_json(intent)}

Playwright UI context:
{as_json(ui_context or {})}

{response_contract("SourceIntelligence")}
"""
