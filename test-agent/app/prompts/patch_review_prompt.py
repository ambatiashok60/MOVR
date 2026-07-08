from __future__ import annotations

from app.prompts.prompt_sections import as_json, response_contract
from app.schemas.code_patch import PatchSet
from app.schemas.validation_result import ValidationResult


def build_repair_prompt(patches: PatchSet, validation: ValidationResult) -> str:
    return f"""
You are repairing generated Playwright patches after validation failure.

Rules:
- Fix only generated patch scope.
- Do not modify unrelated repository files.
- Return structured patches only.

Current patches:
{as_json(patches)}

Validation result:
{as_json(validation)}

{response_contract("PatchSet")}
"""


def build_critic_prompt(patches: PatchSet) -> str:
    return f"""
You are reviewing generated Playwright patches for beta quality.

Rules:
- Keep only safe, scoped, maintainable patch intent.
- Preserve structured patch format.
- Do not add provider-specific SDK usage.

Patches:
{as_json(patches)}

{response_contract("PatchSet")}
"""
