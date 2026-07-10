from __future__ import annotations

from app.prompts.prompt_sections import (
    as_json,
    curated_inventory,
    curated_ui_context,
    response_contract,
)
from app.schemas.functional_intent import FunctionalIntent
from app.schemas.playwright_ui_context import PlaywrightUiContext
from app.schemas.repository_inventory import RepositoryInventory
from app.schemas.spec_placement import SpecPlacementDecision


def build_spec_placement_prompt(
    inventory: RepositoryInventory,
    intent: FunctionalIntent | None = None,
    ui_context: PlaywrightUiContext | None = None,
    include_contract: bool = True,
) -> str:
    return f"""
You are deciding where a Playwright E2E spec change belongs.

Rules:
- Prefer existing specs only when they own the same business behavior.
- Create a new spec when ownership is unclear or a different module owns the flow.
- Do not choose unit or integration specs for E2E generation.
- Prefer specs that already own the route, screen, fixture, auth setup, mock setup, or page object.
- Explain evidence, rejected alternatives, risk, fallback, and confidence.

Functional intent:
{as_json(intent or {})}

Repository inventory:
{as_json(curated_inventory(inventory))}

Playwright UI context:
{as_json(curated_ui_context(ui_context))}

{response_contract(SpecPlacementDecision) if include_contract else ''}
"""
