"""SSE event envelope with a monotonic per-run sequence number."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.enums import StreamEventType


def _now() -> datetime:
    return datetime.now(timezone.utc)


class StreamEvent(BaseModel):
    run_id: str
    sequence: int
    event_type: StreamEventType
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)

    def to_sse(self) -> str:
        """Render as a Server-Sent-Events frame.

        run_id/sequence are written last so a payload key can never shadow the
        canonical monotonic run sequence (the client dedups on it).
        """
        import json

        data = {**self.payload, "run_id": self.run_id, "sequence": self.sequence}
        body = json.dumps(data, default=str)
        return f"id: {self.sequence}\nevent: {self.event_type.value}\ndata: {body}\n\n"
