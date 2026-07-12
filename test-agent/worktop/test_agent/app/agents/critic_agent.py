from __future__ import annotations

from worktop.test_agent.app.agents.base_agent import BaseAgent
from worktop.core_services.app.utility.custom_logger.logging import logger
from worktop.test_agent.app.prompts.patch_review_prompt import build_critic_prompt
from worktop.test_agent.app.schemas.code_patch import PatchSet
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext


class CriticAgent(BaseAgent):
    agent_name = "critic_agent"

    def review(
        self,
        patches: PatchSet,
        ui_context: PlaywrightUiContext | None = None,
    ) -> PatchSet:
        context = self.log_start("critic")
        try:
            return self.complete_structured(
                prompt=build_critic_prompt(patches, ui_context),
                response_model=PatchSet,
            )
        except Exception as exc:
            logger.exception(
                "[playwright-generation] agent=%s stage=critic status=failed context=%s error=%s",
                self.agent_name,
                context,
                exc,
            )
            raise
