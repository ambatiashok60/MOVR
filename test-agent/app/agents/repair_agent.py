from __future__ import annotations

from app.agents.base_agent import BaseAgent, log_exception, log_performance
from app.prompts.patch_review_prompt import build_repair_prompt
from app.schemas.code_patch import PatchSet
from app.schemas.validation_result import ValidationResult


class RepairAgent(BaseAgent):
    agent_name = "repair_agent"

    @log_performance("repair_agent.repair")
    def repair(self, patches: PatchSet, validation: ValidationResult) -> PatchSet:
        context = self.log_start("repair")
        try:
            return self.complete_structured(
                prompt=build_repair_prompt(patches, validation),
                response_model=PatchSet,
            )
        except Exception as exc:
            log_exception(exc, context=context)
            raise
