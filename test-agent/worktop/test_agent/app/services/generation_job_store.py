"""Job-id correlation and lifecycle store for agent generation.

The existing task-manager runtime is keyed by
``(user_story_hierarchy_id, testcase_id, tenant_id)``. The agent API is keyed by
``job_id``. This store is the small correlation layer that maps a ``job_id`` to
its task identity, lifecycle status, result/error and timestamps.

Responsibilities are intentionally narrow. It owns state only; it does NOT own
the queue, worker, SSE transport or abort registry — those remain in the
production task manager.

This default implementation is an in-memory, lock-guarded dictionary suitable
for a single application worker. With multiple Uvicorn workers or ECS tasks,
submission / worker / SSE / polling must reach the same process (sticky
routing), or this store must move to a shared backend (DB or Redis). See the
migration report, section 13.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from worktop.test_agent.app.schemas.generation_status import (
    JOB_ABORT_REQUESTED,
    JOB_ABORTED,
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_QUEUED,
    JOB_RUNNING,
    TERMINAL_JOB_STATUSES,
)
from worktop.test_agent.utils.logging import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GenerationJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Creation and lookup
    # ------------------------------------------------------------------ #
    def create(
        self,
        *,
        job_id: str,
        user_story_hierarchy_id: int,
        testcase_id: str,
        tenant_id: int,
        user_story_id: str | None = None,
        row_id: int | None = None,
        testcase_name: str = "",
        requested_by: str = "",
        automation_steps_count: int = 0,
        flow_steps_count: int = 0,
    ) -> dict[str, Any]:
        with self._lock:
            if job_id in self._jobs:
                raise ValueError(f"Generation job '{job_id}' already exists")
            record: dict[str, Any] = {
                "job_id": job_id,
                "status": JOB_QUEUED,
                "progress": 0.0,
                "user_story_hierarchy_id": user_story_hierarchy_id,
                "testcase_id": testcase_id,
                "tenant_id": tenant_id,
                "user_story_id": user_story_id,
                "row_id": row_id,
                "testcase_name": testcase_name,
                "requested_by": requested_by,
                "automation_steps_count": automation_steps_count,
                "flow_steps_count": flow_steps_count,
                "result": None,
                "error": None,
                "abort_requested": False,
                "created_at": _utcnow(),
                "started_at": None,
                "completed_at": None,
            }
            self._jobs[job_id] = record
            return dict(record)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._jobs.get(job_id)
            return dict(record) if record is not None else None

    # ------------------------------------------------------------------ #
    # Lifecycle transitions
    # ------------------------------------------------------------------ #
    def mark_running(self, job_id: str) -> None:
        with self._lock:
            record = self._active(job_id)
            if record is None:
                return
            record["status"] = JOB_RUNNING
            if record["started_at"] is None:
                record["started_at"] = _utcnow()

    def mark_progress(self, job_id: str, progress: float) -> None:
        with self._lock:
            record = self._active(job_id)
            if record is None:
                return
            record["progress"] = max(0.0, min(1.0, float(progress)))

    def complete(self, job_id: str, result: Any = None) -> None:
        with self._lock:
            record = self._active(job_id)
            if record is None:
                return
            record["status"] = JOB_COMPLETED
            record["result"] = result
            record["progress"] = 1.0
            record["completed_at"] = _utcnow()

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            record = self._active(job_id)
            if record is None:
                return
            record["status"] = JOB_FAILED
            record["error"] = error
            record["completed_at"] = _utcnow()

    def mark_abort_requested(self, job_id: str) -> None:
        with self._lock:
            record = self._active(job_id)
            if record is None:
                return
            record["abort_requested"] = True
            record["status"] = JOB_ABORT_REQUESTED

    def abort(self, job_id: str, error: str | None = None) -> None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                logger.debug("abort called for unknown job_id=%s", job_id)
                return
            if record["status"] in TERMINAL_JOB_STATUSES:
                return
            record["status"] = JOB_ABORTED
            record["error"] = error
            record["completed_at"] = _utcnow()

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _active(self, job_id: str) -> dict[str, Any] | None:
        """Return the live record if it exists and is not already terminal.

        Callers hold ``self._lock``. Transitions on an already-terminal job are
        ignored so a late worker callback cannot resurrect a finished job.
        """
        record = self._jobs.get(job_id)
        if record is None:
            logger.debug("update for unknown job_id=%s", job_id)
            return None
        if record["status"] in TERMINAL_JOB_STATUSES:
            logger.debug(
                "ignoring update for terminal job_id=%s status=%s",
                job_id,
                record["status"],
            )
            return None
        return record


# Process-local singleton used by the routes and the task-manager executor.
generation_job_store = GenerationJobStore()
