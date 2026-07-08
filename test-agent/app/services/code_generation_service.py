from __future__ import annotations

from typing import Any

from worktop.core_services.app.utility.custom_logger.log_helpers import (
    log_card_simple,
    log_exception,
    log_metric,
    log_step,
)
from worktop.core_services.app.utility.custom_logger.logging import (
    log_performance,
    logger,
)

from app.agents.code_generation_agent import CodeGenerationAgent
from app.llm.llm_client import LLMClient
from app.schemas.code_patch import PatchSet
from app.schemas.spec_placement import SpecPlacementDecision
from app.schemas.test_action_decision import TestActionDecision


class CodeGenerationService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.agent = CodeGenerationAgent(llm_client=llm_client)

    @log_performance("code_generation_service.generate")
    def generate(
        self,
        placement: SpecPlacementDecision,
        action: TestActionDecision,
    ) -> PatchSet:
        log_step("code_generation_service_started", {"action": action.action})
        try:
            patches = self.agent.generate(placement, action)
            log_metric("generated_patch_count", len(patches.patches))
            return patches
        except Exception as exc:
            log_exception(exc, context={"stage": "code_generation"})
            raise
