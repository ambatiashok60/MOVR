from __future__ import annotations

from worktop.test_agent.app.agents.base_agent import BaseAgent, logger
from worktop.test_agent.app.prompts.patch_review_prompt import build_repair_prompt
from worktop.test_agent.app.schemas.code_patch import PatchSet
from worktop.test_agent.app.schemas.validation_result import ValidationResult


class RepairAgent(BaseAgent):
    agent_name = "repair_agent"

    def repair(self, patches: PatchSet, validation: ValidationResult) -> PatchSet:
        context = self.log_start("repair")
        try:
            return self.complete_structured(
                prompt=build_repair_prompt(patches, validation),
                response_model=PatchSet,
            )
        except Exception as exc:
            logger.exception(
                "[playwright-generation] agent=%s stage=repair status=failed context=%s error=%s",
                self.agent_name,
                context,
                exc,
            )
            raise
