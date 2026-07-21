from __future__ import annotations

from worktop.test_agent.app.agents.base_agent import BaseAgent
from worktop.core_services.app.utility.custom_logger.logging import logger
from worktop.test_agent.app.prompts.code_generation_prompt import build_code_generation_prompt
from worktop.test_agent.app.schemas.behavioral_test_unit import AnchorFlowContext, ExistingTestContext
from worktop.test_agent.app.schemas.code_patch import PatchSet
from worktop.test_agent.app.schemas.flow_merge import FlowMergePlan
from worktop.test_agent.app.schemas.locator_decision import LocatorDecision
from worktop.test_agent.app.schemas.ownership_resolution import OwnershipResolution
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.spec_placement import SpecPlacementDecision
from worktop.test_agent.app.schemas.test_action_decision import TestActionDecision
from worktop.test_agent.app.schemas.exploration import PatchSetTurn


class CodeGenerationAgent(BaseAgent):
    agent_name = "code_generation_agent"

    def generate(
        self,
        placement: SpecPlacementDecision,
        action: TestActionDecision,
        ui_context: PlaywrightUiContext | None = None,
        existing_test_context: ExistingTestContext | None = None,
        flow_plan: FlowMergePlan | None = None,
        ownership: OwnershipResolution | None = None,
        anchor_flow_context: AnchorFlowContext | None = None,
        locator_decisions: list[LocatorDecision] | None = None,
        repo_path: str | None = None,
    ) -> PatchSet:
        context = self.log_start("code_generation")
        try:
            prompt = build_code_generation_prompt(
                placement,
                action,
                ui_context,
                existing_test_context,
                flow_plan,
                ownership,
                anchor_flow_context,
                locator_decisions,
                include_contract=False,
            )
            prompt += (
                "\n\nBefore emitting patches, READ every page object, fixture, or "
                "helper you are about to reference so all imports and member calls "
                "are real, not guessed. State your reasoning each turn and a reason "
                "for every file you request."
            )
            return self.complete_with_exploration(
                prompt, PatchSetTurn, repo_path or "."
            )
        except Exception as exc:
            logger.exception(
                "[playwright-generation] agent=%s stage=code_generation status=failed context=%s error=%s",
                self.agent_name,
                context,
                exc,
            )
            raise
