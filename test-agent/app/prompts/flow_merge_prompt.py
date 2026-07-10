from __future__ import annotations

from app.prompts.prompt_sections import as_json, response_contract
from app.schemas.behavioral_test_unit import ExistingTestContext
from app.schemas.flow_merge import FlowMergePlan
from app.schemas.functional_intent import FunctionalIntent


def build_flow_merge_prompt(
    intent: FunctionalIntent,
    existing_test_context: ExistingTestContext | None = None,
) -> str:
    return f"""
You are planning how to merge new behavior into an existing stable Playwright flow.

Rules:
- Derive the stable_region and preserved_steps from the Existing test context source, not from the intent.
- preserved_steps must be concrete steps that already exist in the Existing test context and must survive unchanged.
- added_steps are only the steps the functional intent needs that are not already proven.
- Preserve proven setup and navigation.
- Add only missing behavior.
- Do not insert random lines.
- Separate stable region from extension region.
- Explain evidence, rejected alternatives, risk, fallback, and confidence in the decision_trace.

Functional intent:
{as_json(intent)}

Existing test context (source of the proven flow):
{as_json(existing_test_context or {})}

{response_contract(FlowMergePlan)}
"""
