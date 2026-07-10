from __future__ import annotations

from app.prompts.prompt_sections import as_json, response_contract
from app.schemas.locator_decision import LocatorDecisionSet
from app.schemas.source_intelligence import SourceIntelligence


def build_locator_reasoning_prompt(source: SourceIntelligence) -> str:
    return f"""
You are choosing Playwright locators from source evidence.

Rules:
- Do not invent selectors without source evidence.
- Prefer accessible locators and stable testing attributes.
- Explain alternatives rejected and confidence.

Source intelligence:
{as_json(source)}

{response_contract(LocatorDecisionSet)}
"""
