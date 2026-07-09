from __future__ import annotations

from app.agents.base_agent import BaseAgent, logger
from app.prompts.code_generation_prompt import build_code_generation_prompt
from app.schemas.behavioral_test_unit import AnchorFlowContext, ExistingTestContext
from app.schemas.code_patch import PatchSet
from app.schemas.flow_merge import FlowMergePlan
from app.schemas.locator_decision import LocatorDecision
from app.schemas.ownership_resolution import OwnershipResolution
from app.schemas.playwright_ui_context import PlaywrightUiContext
from app.schemas.spec_placement import SpecPlacementDecision
from app.schemas.test_action_decision import TestActionDecision


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
    ) -> PatchSet:
        context = self.log_start("code_generation")
        try:
            return self.complete_structured(
                prompt=build_code_generation_prompt(
                    placement,
                    action,
                    ui_context,
                    existing_test_context,
                    flow_plan,
                    ownership,
                    anchor_flow_context,
                    locator_decisions,
                ),
                response_model=PatchSet,
            )
        except Exception as exc:
            logger.exception(
                "[playwright-generation] agent=%s stage=code_generation status=failed context=%s error=%s",
                self.agent_name,
                context,
                exc,
            )
            raise
