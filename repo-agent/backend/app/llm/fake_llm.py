"""Deterministic LLM used for tests and the local preview.

It drives a realistic Plan-Act-Observe-Decide flow without any network:
- Ask mode: inspect -> search -> respond (read-only).
- Agent mode: inspect -> search -> write a namespaced scratch note -> validate -> respond.

The scratch note (`REPO_AGENT_NOTES.md`) is a non-destructive, clearly-namespaced
mutation, so agent mode is safe to demo against a real workspace.
"""

from __future__ import annotations

import uuid
from typing import AsyncIterator

from app.models.enums import AgentMode, PlanStepStatus, ResponseBatchType
from app.models.plan import ExecutionPlan, PlanStep
from app.models.response import ResponseSection
from app.models.tool import AgentDecision, ToolCall

_STOPWORDS = {"the", "a", "an", "to", "in", "of", "and", "or", "is", "are", "fix",
              "please", "for", "on", "with", "it", "this", "that", "not", "some", "cases"}


def _keywords(message: str, limit: int = 4) -> list[str]:
    words = [w.strip(".,:;!?()[]").lower() for w in message.split()]
    picked = [w for w in words if len(w) > 3 and w not in _STOPWORDS]
    return picked[:limit] or ["status"]


class FakeLLM:
    """Implements the LLMClient protocol deterministically."""

    async def create_plan(self, *, user_request: str, mode: AgentMode, repo_summary: dict) -> ExecutionPlan:
        steps = [
            PlanStep(step_id="step_1", title="Understand the request",
                     objective="Interpret the user's goal", status=PlanStepStatus.COMPLETED,
                     result_summary="Parsed intent and keywords"),
            PlanStep(step_id="step_2", title="Inspect the repository",
                     objective="Locate the relevant area", status=PlanStepStatus.IN_PROGRESS,
                     suggested_tools=["list_directory", "search_code"]),
            PlanStep(step_id="step_3", title="Identify affected code",
                     objective="Trace the code path", suggested_tools=["read_file", "find_symbol"]),
        ]
        if mode == AgentMode.AGENT:
            steps.append(PlanStep(step_id="step_4", title="Apply targeted changes",
                                  objective="Record a namespaced change note",
                                  suggested_tools=["create_file"]))
            steps.append(PlanStep(step_id="step_5", title="Validate",
                                  objective="Run targeted validation",
                                  suggested_tools=["run_tests"]))
        return ExecutionPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            goal=user_request.strip()[:120] or "Repository request",
            mode=mode, steps=steps, current_step_id="step_2", revision=1,
        )

    async def next_decision(self, *, user_request: str, mode: AgentMode, plan: ExecutionPlan,
                            observations: list[str], repo_summary: dict) -> AgentDecision:
        kw = _keywords(user_request)
        step = len(observations)

        if mode == AgentMode.ASK:
            script = [
                ("tool_call", ToolCall(tool_call_id=self._tid(), tool_name="list_directory",
                                       arguments={"path": ".", "depth": 1}, plan_step_id="step_2")),
                ("tool_call", ToolCall(tool_call_id=self._tid(), tool_name="search_code",
                                       arguments={"query": kw[0]}, plan_step_id="step_2")),
            ]
        else:
            script = [
                ("tool_call", ToolCall(tool_call_id=self._tid(), tool_name="list_directory",
                                       arguments={"path": ".", "depth": 1}, plan_step_id="step_2")),
                ("tool_call", ToolCall(tool_call_id=self._tid(), tool_name="search_code",
                                       arguments={"query": kw[0]}, plan_step_id="step_3")),
                ("tool_call", ToolCall(tool_call_id=self._tid(), tool_name="create_file",
                                       arguments={
                                           "path": "REPO_AGENT_NOTES.md",
                                           "content": self._note(user_request, kw),
                                           "overwrite": True,
                                       }, plan_step_id="step_4")),
                ("validate", None),
            ]

        if step < len(script):
            action, tool_call = script[step]
            return AgentDecision(action=action, tool_call=tool_call, reason=f"scripted step {step}")
        return AgentDecision(action="respond", reason="sufficient context gathered")

    async def plan_response_sections(self, *, user_request: str, mode: AgentMode,
                                     observations: list[str]) -> list[ResponseSection]:
        sections = [
            ResponseSection(type=ResponseBatchType.SUMMARY, title="Summary"),
            ResponseSection(type=ResponseBatchType.REPOSITORY_FINDINGS, title="Repository findings"),
        ]
        if mode == AgentMode.AGENT:
            sections.append(ResponseSection(type=ResponseBatchType.CODE_CHANGE,
                                            title="Changes to REPO_AGENT_NOTES.md"))
            sections.append(ResponseSection(type=ResponseBatchType.VALIDATION, title="Validation"))
        else:
            sections.append(ResponseSection(type=ResponseBatchType.CODE_SUGGESTION,
                                            title="Suggested change"))
        return sections

    async def stream_section(self, *, section: ResponseSection, shared_context: dict) -> AsyncIterator[str]:
        request = shared_context.get("user_request", "your request")
        kw = shared_context.get("keywords", ["status"])
        chunks = self._section_text(section, request, kw)
        for chunk in chunks:
            yield chunk

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _tid() -> str:
        return f"tool_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _note(request: str, kw: list[str]) -> str:
        return (
            "# RepoAgent change note\n\n"
            f"Request: {request.strip()}\n\n"
            f"Keywords: {', '.join(kw)}\n\n"
            "This note was generated by the RepoAgent agent-mode demo (FakeLLM).\n"
        )

    @staticmethod
    def _section_text(section: ResponseSection, request: str, kw: list[str]) -> list[str]:
        if section.type == ResponseBatchType.SUMMARY:
            return [f"I analysed **{request.strip()[:80]}**. ",
                    f"The relevant area centres on `{kw[0]}` handling."]
        if section.type == ResponseBatchType.REPOSITORY_FINDINGS:
            return ["\n\nI inspected the repository structure and searched for ",
                    f"`{kw[0]}`. The top matches point at the status-update path."]
        if section.type == ResponseBatchType.CODE_SUGGESTION:
            return ["\n\nSuggested change (proposal only):\n\n",
                    "```python\n", "def update_status(hierarchy_id, status):\n",
                    "    return repo.update_by_hierarchy_id(hierarchy_id, status)\n", "```\n"]
        if section.type == ResponseBatchType.CODE_CHANGE:
            return ["\n\n### `REPO_AGENT_NOTES.md`\n\n",
                    "```diff\n", "+ # RepoAgent change note\n",
                    f"+ Request: {request.strip()[:60]}\n", "```\n"]
        if section.type == ResponseBatchType.VALIDATION:
            return ["\n\nValidation: targeted checks **passed**."]
        return ["\n\nDone."]
