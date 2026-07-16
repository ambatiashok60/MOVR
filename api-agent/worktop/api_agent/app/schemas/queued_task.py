from __future__ import annotations

from pydantic import BaseModel


class QueuedTask(BaseModel):
    queued: bool = True
    task_id: str
