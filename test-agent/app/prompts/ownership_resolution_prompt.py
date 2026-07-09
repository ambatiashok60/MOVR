from __future__ import annotations

from app.prompts.prompt_sections import as_json, response_contract
from app.schemas.functional_intent import FunctionalIntent
from app.schemas.ownership_resolution import OwnershipResolution
from app.schemas.repository_inventory import RepositoryInventory
from app.schemas.source_intelligence import SourceIntelligence


def build_ownership_resolution_prompt(
    inventory: RepositoryInventory,
    source: SourceIntelligence | None = None,
    intent: FunctionalIntent | None = None,
) -> str:
    return f"""
You are deciding where new locators, methods, helpers, or fixtures belong.

Rules:
- Decide ownership for the specific locators and interactions this change needs (see the needed locators/components below), not generically.
- Use page objects when the repo has a page object convention.
- Use helpers or fixtures when existing conventions indicate shared behavior.
- Use the spec only when there is no better owner.
- Reuse an existing owner (set create_new=false) when one already covers the same screen or component the needed locators belong to.
- Create a new owner (set create_new=true) only when no existing page object, helper, or fixture covers the target screen and the repo convention supports adding one; put the intended new file in owner_path.
- Explain evidence, rejected alternatives, risk, fallback, and confidence in the decision_trace.

Functional intent:
{as_json(intent or {})}

Needed locators and components (source evidence):
{as_json(source or {})}

Repository inventory:
{as_json(inventory)}

{response_contract(OwnershipResolution)}
"""
