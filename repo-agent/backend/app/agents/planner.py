"""Creates the initial plan (via the LLM) and evolves it as observations arrive.

Plan updates are deterministic: complete the active step, advance to the next
incomplete one, bump the revision. The plan is data that grows with discovery,
not a fixed template.
"""

from __future__ import annotations

from app.llm.base import LLMClient
from app.models.enums import AgentMode, PlanStepStatus
from app.models.plan import ExecutionPlan


class Planner:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def create_plan(self, *, user_request: str, mode: AgentMode, repo_summary: dict) -> ExecutionPlan:
        return await self._llm.create_plan(
            user_request=user_request, mode=mode, repo_summary=repo_summary
        )

    def advance(self, plan: ExecutionPlan, observation_summary: str) -> ExecutionPlan:
        current = plan.step(plan.current_step_id) if plan.current_step_id else None
        if current:
            current.status = PlanStepStatus.COMPLETED
            current.result_summary = observation_summary[:200]

        nxt = plan.first_incomplete()
        if nxt:
            nxt.status = PlanStepStatus.IN_PROGRESS
            plan.current_step_id = nxt.step_id
        else:
            plan.current_step_id = None

        plan.revision += 1
        return plan
