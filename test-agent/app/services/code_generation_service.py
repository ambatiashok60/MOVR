from __future__ import annotations

import logging


from app.agents.code_generation_agent import CodeGenerationAgent
from app.llm.llm_client import LLMClient
from app.schemas.behavioral_test_unit import AnchorFlowContext, ExistingTestContext
from app.schemas.code_patch import PatchSet
from app.schemas.flow_merge import FlowMergePlan
from app.schemas.locator_decision import LocatorDecision
from app.schemas.ownership_resolution import OwnershipResolution
from app.schemas.playwright_ui_context import PlaywrightUiContext
from app.schemas.spec_placement import SpecPlacementDecision
from app.schemas.test_action_decision import TestActionDecision

logger = logging.getLogger(__name__)


class CodeGenerationService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.agent = CodeGenerationAgent(llm_client=llm_client)

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
        logger.info(
            "[playwright-generation] stage=code_generation_service status=started "
            "action=%s target_spec=%s existing_target=%s existing_lines=%s-%s",
            action.action,
            placement.target_spec_file,
            existing_test_context.file_path if existing_test_context else "none",
            existing_test_context.start_line if existing_test_context else None,
            existing_test_context.end_line if existing_test_context else None,
        )
        try:
            patches = self.agent.generate(
                placement,
                action,
                ui_context,
                existing_test_context,
                flow_plan,
                ownership,
                anchor_flow_context,
                locator_decisions,
                repo_path,
            )
            logger.info(
                "[playwright-generation] stage=code_generation_service status=completed "
                f"patches={len(patches.patches)}"
            )
            for patch in patches.patches:
                logger.info(
                    "[playwright-generation] stage=code_generation_service patch path=%s "
                    "operation=%s lines=%s-%s content_chars=%s reason=%s",
                    patch.path,
                    patch.operation,
                    patch.start_line,
                    patch.end_line,
                    len(patch.content),
                    patch.reason,
                )
            return patches
        except Exception as exc:
            logger.info(
                "[playwright-generation] stage=code_generation_service status=failed "
                f"error={exc}"
            )
            logger.exception(
                "[playwright-generation] stage=code_generation_service status=failed error=%s",
                exc,
            )
            raise
