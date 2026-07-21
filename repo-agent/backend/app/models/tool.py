"""Tool definitions, calls, and bounded results."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import AgentMode


class ToolDefinition(BaseModel):
    name: str
    description: str
    allowed_modes: set[AgentMode]
    timeout_seconds: int = 120
    mutates_workspace: bool = False


class ToolCall(BaseModel):
    tool_call_id: str
    tool_name: str
    arguments: dict = Field(default_factory=dict)
    plan_step_id: str | None = None


class ToolResult(BaseModel):
    tool_call_id: str
    tool_name: str
    success: bool
    summary: str
    content: str | None = None
    truncated: bool = False
    continuation_token: str | None = None
    metadata: dict = Field(default_factory=dict)
    duration_ms: int = 0


class AgentDecision(BaseModel):
    """What the decision engine / LLM wants to do next."""

    action: str  # tool_call | validate | respond | fail
    tool_call: ToolCall | None = None
    reason: str = ""
