"""Asks the LLM what to do next, given the plan and observations so far."""

from __future__ import annotations

from app.llm.base import LLMClient
from app.models.enums import AgentMode
from app.models.plan import ExecutionPlan
from app.models.tool import AgentDecision


class DecisionEngine:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def decide(self, *, user_request: str, mode: AgentMode, plan: ExecutionPlan,
                     observations: list[str], repo_summary: dict) -> AgentDecision:
        return await self._llm.next_decision(
            user_request=user_request, mode=mode, plan=plan,
            observations=observations, repo_summary=repo_summary,
        )
