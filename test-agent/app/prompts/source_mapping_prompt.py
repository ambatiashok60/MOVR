from __future__ import annotations

from app.prompts.prompt_sections import as_json, response_contract
from app.schemas.functional_intent import FunctionalIntent


def build_source_mapping_prompt(intent: FunctionalIntent) -> str:
    return f"""
You are mapping functional intent to source evidence.

Rules:
- Identify routes, components, services, and locator evidence.
- Evidence must be grounded in repository source when available.
- Leave sections empty when there is no evidence.

Functional intent:
{as_json(intent)}

{response_contract("SourceIntelligence")}
"""
