"""Run request/response contracts and the run view + structured error model."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import AgentMode, RunStatus


class AgentRunRequest(BaseModel):
    workspace_path: str
    conversation_id: str | None = None
    mode: AgentMode
    message: str = Field(min_length=1)

    # Idempotency key — a retried POST with the same value must not create a
    # second run. See ConversationService/agent_routes.
    client_request_id: str | None = None

    # AWS overrides (optional; fall back to settings when empty).
    aws_profile: str | None = None
    aws_region: str | None = None
    model_id: str | None = None

    enable_validation: bool = True
    max_agent_iterations: int = 20


class CreateRunResponse(BaseModel):
    run_id: str
    conversation_id: str
    status: RunStatus
    events_url: str


class AgentRunError(BaseModel):
    code: str
    message: str
    recoverable: bool = False
    retry_action: str | None = None  # reconnect | reauthenticate | resume_run | start_new_run | none
    details: dict = Field(default_factory=dict)


class AgentRunView(BaseModel):
    """Authoritative run state returned by GET /agent-runs/{id}."""

    run_id: str
    conversation_id: str
    workspace_path: str
    mode: AgentMode
    status: RunStatus
    agent_state: str | None = None
    last_event_sequence: int = 0
    plan_revision: int = 0
    tool_call_count: int = 0
    files_read_count: int = 0
    files_modified_count: int = 0
    error: AgentRunError | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_activity_at: datetime | None = None
