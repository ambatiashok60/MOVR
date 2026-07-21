"""Real AWS Bedrock client implementing the LLMClient protocol.

The important, unit-testable part is `invoke()`: the try -> reset+retry ->
sso login+retry credential-recovery ladder from the design (§4). The Converse
integration itself can only be exercised against real AWS, so it is written to
AWS's documented Converse API shape and kept intentionally simple.

Callbacks let the orchestrator surface `aws_reauthentication_required` /
`aws_reauthenticated` SSE events without coupling this module to streaming.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Awaitable, Callable

from app.config import settings
from app.llm.aws_session_manager import AwsSessionManager
from app.llm.exceptions import is_credential_error
from app.llm.sso_login_service import SsoLoginService
from app.logging.agent_logger import agent_logger
from app.models.enums import AgentMode, ResponseBatchType
from app.models.plan import ExecutionPlan, PlanStep
from app.models.response import ResponseSection
from app.models.tool import AgentDecision, ToolCall

ReauthCallback = Callable[[str], Awaitable[None]]


class BedrockClient:
    def __init__(
        self,
        session_manager: AwsSessionManager,
        login_service: SsoLoginService,
        profile_name: str,
        model_id: str,
        on_reauth_required: ReauthCallback | None = None,
        on_reauthenticated: ReauthCallback | None = None,
    ) -> None:
        self.session_manager = session_manager
        self.login_service = login_service
        self.profile_name = profile_name
        self.model_id = model_id
        self._on_reauth_required = on_reauth_required
        self._on_reauthenticated = on_reauthenticated

    # --- credential-resilient invocation (§4) ------------------------------
    async def invoke(self, messages: list[dict], system: str | None = None) -> str:
        try:
            return await self._invoke_once(messages, system)
        except Exception as exc:  # noqa: BLE001 - classified below
            if not is_credential_error(exc):
                raise

        # 1) reset session + retry once (refreshes short-lived credentials).
        agent_logger.aws_refresh_started(
            {"profile": self.profile_name, "cause": "credential_error", "action": "reset session",
             "retry": "1 of 2"})
        self.session_manager.reset()
        try:
            result = await self._invoke_once(messages, system)
            agent_logger.aws_refresh_completed({"profile": self.profile_name, "result": "session restored"})
            return result
        except Exception as exc:  # noqa: BLE001
            if not is_credential_error(exc):
                raise

        # 2) interactive SSO login (SSO session itself expired), then retry.
        if self._on_reauth_required:
            await self._on_reauth_required(self.profile_name)
        await self.login_service.login(self.profile_name)
        self.session_manager.reset()
        result = await self._invoke_once(messages, system)
        if self._on_reauthenticated:
            await self._on_reauthenticated(self.profile_name)
        agent_logger.aws_refresh_completed(
            {"profile": self.profile_name, "action": "aws sso login", "result": "session restored"})
        return result

    async def _invoke_once(self, messages: list[dict], system: str | None) -> str:
        client = self.session_manager.get_bedrock_client()

        def _call() -> str:
            kwargs = {
                "modelId": self.model_id,
                "messages": messages,
                "inferenceConfig": {"maxTokens": 2000, "temperature": 0.2},
            }
            if system:
                kwargs["system"] = [{"text": system}]
            response = client.converse(**kwargs)
            parts = response["output"]["message"]["content"]
            return "".join(p.get("text", "") for p in parts)

        return await asyncio.wait_for(
            asyncio.to_thread(_call), timeout=settings.llm_request_timeout_seconds
        )

    # --- LLMClient protocol ------------------------------------------------
    async def create_plan(self, *, user_request: str, mode: AgentMode, repo_summary: dict) -> ExecutionPlan:
        system = (
            "You are a repository engineering planner. Return ONLY JSON of the form "
            '{"goal": str, "steps": [{"step_id": str, "title": str, "objective": str, '
            '"suggested_tools": [str]}]}.'
        )
        prompt = f"Mode: {mode.value}\nRepo: {json.dumps(repo_summary)}\nRequest: {user_request}"
        raw = await self.invoke([{"role": "user", "content": [{"text": prompt}]}], system)
        data = _safe_json(raw, default={"goal": user_request, "steps": []})
        steps = [
            PlanStep(step_id=s.get("step_id", f"step_{i+1}"), title=s.get("title", "Step"),
                     objective=s.get("objective", ""), suggested_tools=s.get("suggested_tools", []))
            for i, s in enumerate(data.get("steps", []))
        ] or [PlanStep(step_id="step_1", title="Inspect repository", objective=user_request)]
        return ExecutionPlan(plan_id="plan_bedrock", goal=data.get("goal", user_request),
                             mode=mode, steps=steps, current_step_id=steps[0].step_id)

    async def next_decision(self, *, user_request: str, mode: AgentMode, plan: ExecutionPlan,
                            observations: list[str], repo_summary: dict) -> AgentDecision:
        system = (
            "Decide the next action. Return ONLY JSON: "
            '{"action": "tool_call|validate|respond|fail", "tool_name": str, "arguments": obj, "reason": str}.'
        )
        prompt = (
            f"Mode: {mode.value}\nGoal: {plan.goal}\n"
            f"Observations so far ({len(observations)}):\n" + "\n".join(observations[-5:])
        )
        raw = await self.invoke([{"role": "user", "content": [{"text": prompt}]}], system)
        data = _safe_json(raw, default={"action": "respond"})
        action = data.get("action", "respond")
        tool_call = None
        if action == "tool_call":
            import uuid
            tool_call = ToolCall(tool_call_id=f"tool_{uuid.uuid4().hex[:8]}",
                                 tool_name=data.get("tool_name", "read_file"),
                                 arguments=data.get("arguments", {}))
        return AgentDecision(action=action, tool_call=tool_call, reason=data.get("reason", ""))

    async def plan_response_sections(self, *, user_request: str, mode: AgentMode,
                                     observations: list[str]) -> list[ResponseSection]:
        sections = [ResponseSection(type=ResponseBatchType.SUMMARY, title="Summary"),
                    ResponseSection(type=ResponseBatchType.REPOSITORY_FINDINGS, title="Repository findings")]
        if mode == AgentMode.AGENT:
            sections.append(ResponseSection(type=ResponseBatchType.CODE_CHANGE, title="Changes"))
            sections.append(ResponseSection(type=ResponseBatchType.VALIDATION, title="Validation"))
        else:
            sections.append(ResponseSection(type=ResponseBatchType.CODE_SUGGESTION, title="Suggested change"))
        return sections

    async def stream_section(self, *, section: ResponseSection, shared_context: dict) -> AsyncIterator[str]:
        system = f"Write the '{section.type.value}' section in Markdown. Be concise and grounded."
        prompt = json.dumps({k: v for k, v in shared_context.items() if k != "raw"})[:4000]
        text = await self.invoke([{"role": "user", "content": [{"text": prompt}]}], system)
        # Bedrock converse is buffered here; chunk it for the SSE delta contract.
        for i in range(0, len(text), 40):
            yield text[i:i + 40]


def _safe_json(raw: str, default: dict) -> dict:
    raw = raw.strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass
    return default
