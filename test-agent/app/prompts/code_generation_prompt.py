from __future__ import annotations

from app.prompts.prompt_sections import as_json, response_contract
from app.schemas.spec_placement import SpecPlacementDecision
from app.schemas.test_action_decision import TestActionDecision


def build_code_generation_prompt(
    placement: SpecPlacementDecision,
    action: TestActionDecision,
) -> str:
    return f"""
You are generating structured Playwright patch intent.

Rules:
- Return structured patches only.
- Do not overwrite whole specs for an extension.
- Do not add raw locators to specs when page objects exist.
- Use create, replace, or append operations only.

Spec placement:
{as_json(placement)}

Test action:
{as_json(action)}

{response_contract("PatchSet")}
"""
