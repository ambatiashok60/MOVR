from __future__ import annotations



from worktop.test_agent.app.agents.flow_merge_agent import FlowMergeAgent
from worktop.test_agent.app.llm.llm_client import LLMClient
from worktop.test_agent.app.schemas.behavioral_test_unit import ExistingTestContext
from worktop.test_agent.app.schemas.flow_merge import FlowMergePlan
from worktop.test_agent.app.schemas.functional_intent import FunctionalIntent
from worktop.test_agent.utils.logging import get_logger

logger = get_logger(__name__)


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
