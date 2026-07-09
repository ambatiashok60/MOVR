from __future__ import annotations

from enum import StrEnum


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    ABORTING = "aborting"
    ABORTED = "aborted"
    COMPLETED = "completed"
    FAILED = "failed"
