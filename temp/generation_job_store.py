"""
Thread-safe in-memory lifecycle store for Test Agent generation jobs.

This store is for HTTP status and local lifecycle tracking. It is not a
replacement for the existing Script Generator SSE subscriber registry.

For multi-process production deployment, replace the internal dictionary with
a shared persistence mechanism such as the existing platform database or
Redis. The public methods can remain unchanged.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from worktop.test_agent.utils.logging import get_logger

logger = get_logger(__name__)


JOB_QUEUED = "Queued"
JOB_IN_PROGRESS = "InProgress"
JOB_COMPLETED = "Completed"
JOB_FAILED = "Failed"
JOB_ABORTED = "Aborted"

TERMINAL_JOB_STATUSES = {
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_ABORTED,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GenerationJobStore:
    """
    Thread-safe generation-job state store.

    Job identifiers are always normalized to strings.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def create(
        self,
        *,
        job_id: str,
        user_story_hierarchy_id: int,
        testcase_id: str,
        tenant_id: int,
        user_story_id: str | None = None,
        row_id: int | str | None = None,
        testcase_name: str | None = None,
        requested_by: str | None = None,
        automation_steps_count: int = 0,
        flow_steps_count: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a queued job.

        Raises ValueError when the same job_id already exists.
        """
        normalized_job_id = str(job_id)
        now = _utc_now()

        with self._lock:
            if normalized_job_id in self._jobs:
                raise ValueError(
                    f"Generation job already exists: {normalized_job_id}"
                )

            job = {
                "job_id": normalized_job_id,
                "status": JOB_QUEUED,
                "user_story_hierarchy_id": int(
                    user_story_hierarchy_id
                ),
                "testcase_id": str(testcase_id),
                "tenant_id": int(tenant_id),
                "user_story_id": user_story_id,
                "row_id": row_id,
                "testcase_name": testcase_name,
                "requested_by": requested_by,
                "automation_steps_count": int(
                    automation_steps_count
                ),
                "flow_steps_count": int(flow_steps_count),
                "result": None,
                "error": None,
                "metadata": deepcopy(metadata or {}),
                "created_at": now,
                "queued_at": now,
                "started_at": None,
                "completed_at": None,
                "updated_at": now,
            }

            self._jobs[normalized_job_id] = job

            logger.info(
                "Generation job created | "
                "job_id=%s hierarchy_id=%s testcase_id=%s tenant_id=%s",
                normalized_job_id,
                user_story_hierarchy_id,
                testcase_id,
                tenant_id,
            )

            return deepcopy(job)

    def mark_queued(
        self,
        job_id: str,
    ) -> dict[str, Any]:
        """Set an existing non-terminal job to Queued."""
        return self._transition(
            job_id=job_id,
            status=JOB_QUEUED,
            result=None,
            error=None,
        )

    def mark_in_progress(
        self,
        job_id: str,
    ) -> dict[str, Any]:
        """Set a job to InProgress."""
        normalized_job_id = str(job_id)
        now = _utc_now()

        with self._lock:
            job = self._require_job(normalized_job_id)
            self._ensure_not_terminal(job)

            job["status"] = JOB_IN_PROGRESS
            job["started_at"] = job.get("started_at") or now
            job["updated_at"] = now
            job["error"] = None

            logger.info(
                "Generation job started | job_id=%s",
                normalized_job_id,
            )

            return deepcopy(job)

    def complete(
        self,
        job_id: str,
        *,
        result: Any,
    ) -> dict[str, Any]:
        """Set a job to Completed and store its result."""
        normalized_job_id = str(job_id)
        now = _utc_now()

        with self._lock:
            job = self._require_job(normalized_job_id)
            self._ensure_not_terminal(job)

            job["status"] = JOB_COMPLETED
            job["result"] = self._serialize_value(result)
            job["error"] = None
            job["completed_at"] = now
            job["updated_at"] = now

            logger.info(
                "Generation job completed | job_id=%s",
                normalized_job_id,
            )

            return deepcopy(job)

    def fail(
        self,
        job_id: str,
        error: str | BaseException,
    ) -> dict[str, Any]:
        """Set a job to Failed and store a normalized error."""
        normalized_job_id = str(job_id)
        now = _utc_now()

        with self._lock:
            job = self._require_job(normalized_job_id)

            if job["status"] in TERMINAL_JOB_STATUSES:
                return deepcopy(job)

            job["status"] = JOB_FAILED
            job["result"] = None
            job["error"] = {
                "message": str(error),
                "type": type(error).__name__
                if isinstance(error, BaseException)
                else "GenerationError",
            }
            job["completed_at"] = now
            job["updated_at"] = now

            logger.error(
                "Generation job failed | job_id=%s error=%s",
                normalized_job_id,
                error,
            )

            return deepcopy(job)

    def abort(
        self,
        job_id: str,
        *,
        reason: str = "Generation aborted by user.",
    ) -> dict[str, Any]:
        """Set a non-terminal job to Aborted."""
        normalized_job_id = str(job_id)
        now = _utc_now()

        with self._lock:
            job = self._require_job(normalized_job_id)

            if job["status"] in TERMINAL_JOB_STATUSES:
                return deepcopy(job)

            job["status"] = JOB_ABORTED
            job["result"] = None
            job["error"] = {
                "message": reason,
                "type": "GenerationAborted",
            }
            job["completed_at"] = now
            job["updated_at"] = now

            logger.info(
                "Generation job aborted | job_id=%s",
                normalized_job_id,
            )

            return deepcopy(job)

    def get(
        self,
        job_id: str,
    ) -> dict[str, Any] | None:
        """Return a copy of a job or None."""
        with self._lock:
            job = self._jobs.get(str(job_id))
            return deepcopy(job) if job is not None else None

    def require(
        self,
        job_id: str,
    ) -> dict[str, Any]:
        """Return a job or raise KeyError."""
        with self._lock:
            return deepcopy(
                self._require_job(str(job_id))
            )

    def exists(
        self,
        job_id: str,
    ) -> bool:
        with self._lock:
            return str(job_id) in self._jobs

    def list_jobs(
        self,
        *,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return jobs ordered newest-first."""
        with self._lock:
            jobs = list(self._jobs.values())

            if status is not None:
                jobs = [
                    job
                    for job in jobs
                    if job.get("status") == status
                ]

            jobs.sort(
                key=lambda item: item.get("created_at", ""),
                reverse=True,
            )

            return deepcopy(jobs)

    def update_metadata(
        self,
        job_id: str,
        **metadata: Any,
    ) -> dict[str, Any]:
        """Merge additional metadata into an existing job."""
        normalized_job_id = str(job_id)

        with self._lock:
            job = self._require_job(normalized_job_id)
            current_metadata = job.setdefault("metadata", {})
            current_metadata.update(
                self._serialize_value(metadata)
            )
            job["updated_at"] = _utc_now()

            return deepcopy(job)

    def delete(
        self,
        job_id: str,
    ) -> bool:
        """Remove a job from the in-memory store."""
        with self._lock:
            return self._jobs.pop(str(job_id), None) is not None

    def clear_terminal_jobs(self) -> int:
        """Remove all terminal jobs and return the number removed."""
        with self._lock:
            terminal_ids = [
                job_id
                for job_id, job in self._jobs.items()
                if job.get("status") in TERMINAL_JOB_STATUSES
            ]

            for job_id in terminal_ids:
                self._jobs.pop(job_id, None)

            return len(terminal_ids)

    def _transition(
        self,
        *,
        job_id: str,
        status: str,
        result: Any,
        error: Any,
    ) -> dict[str, Any]:
        normalized_job_id = str(job_id)

        with self._lock:
            job = self._require_job(normalized_job_id)
            self._ensure_not_terminal(job)

            job["status"] = status
            job["result"] = self._serialize_value(result)
            job["error"] = self._serialize_value(error)
            job["updated_at"] = _utc_now()

            return deepcopy(job)

    def _require_job(
        self,
        job_id: str,
    ) -> dict[str, Any]:
        job = self._jobs.get(job_id)

        if job is None:
            raise KeyError(
                f"Generation job not found: {job_id}"
            )

        return job

    @staticmethod
    def _ensure_not_terminal(
        job: dict[str, Any],
    ) -> None:
        if job.get("status") in TERMINAL_JOB_STATUSES:
            raise ValueError(
                "Cannot transition terminal generation job "
                f"{job.get('job_id')} from {job.get('status')}."
            )

    @classmethod
    def _serialize_value(
        cls,
        value: Any,
    ) -> Any:
        if value is None:
            return None

        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")

        if isinstance(value, dict):
            return {
                str(key): cls._serialize_value(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [
                cls._serialize_value(item)
                for item in value
            ]

        if isinstance(value, BaseException):
            return {
                "message": str(value),
                "type": type(value).__name__,
            }

        return value


generation_job_store = GenerationJobStore()