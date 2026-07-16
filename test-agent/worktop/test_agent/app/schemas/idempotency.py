from __future__ import annotations

from pydantic import BaseModel, Field


class IdempotencyRecord(BaseModel):
    """A completed generation identified by its input fingerprint."""

    fingerprint: str
    job_id: str
    completed_at: str
    files_changed: list[str] = Field(default_factory=list)
    diff_summary: str = ""
