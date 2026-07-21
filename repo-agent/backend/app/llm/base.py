"""The interface the orchestrator depends on.

Both FakeLLM and BedrockClient implement it, so the agent logic never knows or
cares which provider is active.
"""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from app.models.enums import AgentMode
from app.models.plan import ExecutionPlan
from app.models.response import ResponseSection
from app.models.tool import AgentDecision


@runtime_checkable
class LLMClient(Protocol):
    async def create_plan(
        self, *, user_request: str, mode: AgentMode, repo_summary: dict
    ) -> ExecutionPlan: ...

    async def next_decision(
        self,
        *,
        user_request: str,
        mode: AgentMode,
        plan: ExecutionPlan,
        observations: list[str],
        repo_summary: dict,
    ) -> AgentDecision: ...

    async def plan_response_sections(
        self, *, user_request: str, mode: AgentMode, observations: list[str]
    ) -> list[ResponseSection]: ...

    async def stream_section(
        self, *, section: ResponseSection, shared_context: dict
    ) -> AsyncIterator[str]: ...
