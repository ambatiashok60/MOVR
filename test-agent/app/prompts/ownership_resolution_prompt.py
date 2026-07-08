from __future__ import annotations

from app.prompts.prompt_sections import as_json, response_contract
from app.schemas.repository_inventory import RepositoryInventory


def build_ownership_resolution_prompt(inventory: RepositoryInventory) -> str:
    return f"""
You are deciding where new locators, methods, helpers, or fixtures belong.

Rules:
- Use page objects when the repo has a page object convention.
- Use helpers or fixtures when existing conventions indicate shared behavior.
- Use the spec only when there is no better owner.

Repository inventory:
{as_json(inventory)}

{response_contract("OwnershipResolution")}
"""
