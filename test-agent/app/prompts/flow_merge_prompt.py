from __future__ import annotations

from app.prompts.prompt_sections import as_json, response_contract
from app.schemas.functional_intent import FunctionalIntent


def build_flow_merge_prompt(intent: FunctionalIntent) -> str:
    return f"""
You are planning how to merge new behavior into an existing stable Playwright flow.

Rules:
- Preserve proven setup and navigation.
- Add only missing behavior.
- Do not insert random lines.
- Separate stable region from extension region.

Functional intent:
{as_json(intent)}

{response_contract("FlowMergePlan")}
"""
