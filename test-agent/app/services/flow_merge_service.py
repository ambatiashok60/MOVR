from __future__ import annotations

import logging


from app.agents.flow_merge_agent import FlowMergeAgent
from app.llm.llm_client import LLMClient
from app.schemas.behavioral_test_unit import ExistingTestContext
from app.schemas.flow_merge import FlowMergePlan
from app.schemas.functional_intent import FunctionalIntent

logger = logging.getLogger(__name__)


class FlowMergeService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.agent = FlowMergeAgent(llm_client=llm_client)

    def plan(
        self,
        intent: FunctionalIntent,
        existing_test_context: ExistingTestContext | None = None,
    ) -> FlowMergePlan:
        logger.info(
            "[playwright-generation] stage=flow_merge status=started capability=%s",
            intent.capability,
        )
        try:
            plan = self.agent.plan(intent, existing_test_context)
            logger.info("[playwright-generation] stage=flow_merge status=completed")
            return plan
        except Exception as exc:
            logger.exception("[playwright-generation] stage=flow_merge status=failed error=%s", exc)
            raise
