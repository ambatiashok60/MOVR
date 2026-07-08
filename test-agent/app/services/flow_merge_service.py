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

from app.agents.flow_merge_agent import FlowMergeAgent
from app.llm.llm_client import LLMClient
from app.schemas.flow_merge import FlowMergePlan
from app.schemas.functional_intent import FunctionalIntent


class FlowMergeService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.agent = FlowMergeAgent(llm_client=llm_client)

    @log_performance("flow_merge_service.plan")
    def plan(self, intent: FunctionalIntent) -> FlowMergePlan:
        log_step("flow_merge_service_started", {"capability": intent.capability})
        try:
            return self.agent.plan(intent)
        except Exception as exc:
            log_exception(exc, context={"stage": "flow_merge"})
            raise
