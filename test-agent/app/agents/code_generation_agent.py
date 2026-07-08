from __future__ import annotations

from app.agents.base_agent import BaseAgent, log_exception, log_performance
from app.prompts.code_generation_prompt import build_code_generation_prompt
from app.schemas.code_patch import PatchSet
from app.schemas.playwright_ui_context import PlaywrightUiContext
from app.schemas.spec_placement import SpecPlacementDecision
from app.schemas.test_action_decision import TestActionDecision


class CodeGenerationAgent(BaseAgent):
    agent_name = "code_generation_agent"

    @log_performance("code_generation_agent.generate")
    def generate(
        self,
        placement: SpecPlacementDecision,
        action: TestActionDecision,
        ui_context: PlaywrightUiContext | None = None,
    ) -> PatchSet:
        context = self.log_start("code_generation")
        try:
            return self.complete_structured(
                prompt=build_code_generation_prompt(placement, action, ui_context),
                response_model=PatchSet,
            )
        except Exception as exc:
            log_exception(exc, context=context)
            raise
