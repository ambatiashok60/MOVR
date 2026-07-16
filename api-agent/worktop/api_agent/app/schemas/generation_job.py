from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from worktop.api_agent.app.schemas.event import GenerationEvent
from worktop.api_agent.app.schemas.task_status import TaskStatus


class GenerationJob(BaseModel):
    task_id: str
    key: str | None = None
    task_type: str
    status: TaskStatus
    stage: str = "queued"
    request_payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    abort_requested: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    events: list[GenerationEvent] = Field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
