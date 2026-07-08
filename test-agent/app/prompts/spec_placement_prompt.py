from __future__ import annotations

from app.prompts.prompt_sections import as_json, response_contract
from app.schemas.functional_intent import FunctionalIntent
from app.schemas.repository_inventory import RepositoryInventory


def build_spec_placement_prompt(
    inventory: RepositoryInventory,
    intent: FunctionalIntent | None = None,
) -> str:
    return f"""
You are deciding where a Playwright E2E spec change belongs.

Rules:
- Prefer existing specs only when they own the same business behavior.
- Create a new spec when ownership is unclear or a different module owns the flow.
- Do not choose unit or integration specs for E2E generation.
- Explain evidence, rejected alternatives, risk, fallback, and confidence.

Functional intent:
{as_json(intent or {})}

Repository inventory:
{as_json(inventory)}

{response_contract("SpecPlacementDecision")}
"""
