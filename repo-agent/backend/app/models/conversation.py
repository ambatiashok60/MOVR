"""Conversation, message, and the rolling compaction summary."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.enums import AgentMode


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Message(BaseModel):
    id: str
    conversation_id: str
    role: str  # user | assistant
    content: str
    run_id: str | None = None
    turn_index: int = 0
    created_at: datetime = Field(default_factory=_now)


class ConversationSummary(BaseModel):
    """The compacted rolling memory (§12) — what survives beyond recent turns."""

    goal: str = ""
    repository_context: list[str] = Field(default_factory=list)
    architectural_findings: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    inspected_files: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    validation_results: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    user_constraints: list[str] = Field(default_factory=list)
    current_plan_summary: str = ""


class Conversation(BaseModel):
    id: str
    workspace_path: str
    title: str = "New Chat"
    mode: AgentMode = AgentMode.AGENT
    turn_count: int = 0
    compaction_count: int = 0
    active_summary_id: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
