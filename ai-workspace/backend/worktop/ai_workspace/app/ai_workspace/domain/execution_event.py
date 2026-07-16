from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ExecutionEventType(str, Enum):
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"
    TOOL_CALL = "tool_call"
    MESSAGE = "message"
    COMPLETED = "completed"


@dataclass
class ExecutionEvent:
    """One SSE frame. sse_event_publisher.py serializes this; execution_event_service.py
    is the only thing that constructs it."""

    execution_id: str
    event_type: ExecutionEventType
    label: str
    detail: str | None
    created_at: datetime
