from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class GenerationJob(BaseModel):
    """Public view of a generation job's lifecycle state.

    ``result`` is a serialized dict (see ``_serialize_result`` in the job route)
    rather than the internal ``GenerationResult`` so the API response stays
    decoupled from the internal model.
    """

    job_id: str
    status: str
    progress: float | None = None
    testcase_id: str
    user_story_hierarchy_id: int
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    automation_steps_count: int = 0
    flow_steps_count: int = 0
