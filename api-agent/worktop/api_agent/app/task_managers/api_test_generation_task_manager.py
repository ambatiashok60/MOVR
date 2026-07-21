from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

from worktop.api_agent.app.errors import AbortRequestedError, TaskNotFoundError
from worktop.api_agent.app.schemas.api_scenario_request import GenerateApiScenariosRequest
from worktop.api_agent.app.schemas.api_test_generation_request import (
    GenerateApiTestCodeRequest,
    GenerateApiTestsRequest,
)
from worktop.api_agent.app.schemas.generation_job import GenerationJob
from worktop.api_agent.app.schemas.task_status import TaskStatus
from worktop.api_agent.app.services.generation_orchestrator import GenerationOrchestrator
from worktop.api_agent.app.task_managers.api_test_generation_sse_manager import sse_manager
from worktop.api_agent.app.utils.logging_utils import log_exception, log_step


class ApiTestGenerationTaskManager:
    def __init__(self) -> None:
        self._jobs: dict[str, GenerationJob] = {}
        self._key_to_task_id: dict[str, str] = {}
        self._lock = Lock()
        from worktop.api_agent.app.config import settings
        self._executor = ThreadPoolExecutor(max_workers=settings.worker_count, thread_name_prefix="api-agent")

    def enqueue_scenario_generation(
        self,
        request: GenerateApiScenariosRequest,
        db: Any | None = None,
    ) -> str:
        key = make_api_scenario_key(
            request.tenant_id or 1,
            request.user_story_hierarchy_id,
            request.user_story_id,
        )
        existing = self._reusable_task_id(key, request.model_dump())
        if existing:
            return existing
        task_id = self._create_job("api_scenario_generation", request.model_dump(), key)
        self._executor.submit(self._run_scenario_generation, task_id, request, db)
        return task_id

    def enqueue_test_code_generation(
        self,
        request: GenerateApiTestCodeRequest,
        db: Any | None = None,
    ) -> str:
        _require_resolved_repo_path(request)
        key = make_api_test_key(
            request.tenant_id or 1,
            request.user_story_hierarchy_id,
            request.api_scenario_id,
            None,
        )
        existing = self._reusable_task_id(key, request.model_dump())
        if existing:
            return existing
        task_id = self._create_job("api_test_code_generation", request.model_dump(), key)
        self._executor.submit(self._run_test_code_generation, task_id, request, db)
        return task_id

    def enqueue_api_tests(
        self,
        request: GenerateApiTestsRequest,
        db: Any | None = None,
        task_id: str | None = None,
    ) -> str:
        _require_resolved_repo_path(request)
        key = make_api_test_key(
            request.tenant_id or 1,
            request.user_story_hierarchy_id,
            request.testcase_id,
            request.row_id,
        )
        existing = self._reusable_task_id(key, request.model_dump())
        if existing:
            return existing
        task_id = self._create_job("api_test_generation", request.model_dump(), key, task_id)
        self._executor.submit(
            self._run_test_code_generation,
            task_id,
            request.to_code_request(),
            db,
        )
        return task_id

    def get_job(self, task_id: str) -> GenerationJob:
        with self._lock:
            job = self._jobs.get(task_id)
            if job is None:
                raise TaskNotFoundError(task_id)
            job.events = sse_manager.get_events(task_id)
            return job.model_copy(deep=True)

    def get_job_by_key(self, key: str) -> GenerationJob:
        with self._lock:
            task_id = self._key_to_task_id.get(key)
        if task_id is None:
            raise TaskNotFoundError(key)
        return self.get_job(task_id)

    def abort(self, task_id: str) -> GenerationJob:
        with self._lock:
            job = self._jobs.get(task_id)
            if job is None:
                raise TaskNotFoundError(task_id)
            if job.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.ABORTED}:
                return job.model_copy(deep=True)
            job.abort_requested = True
            job.status = TaskStatus.ABORTING
            job.stage = "aborting"
            job.touch()
        self._publish(task_id, "aborting", "aborting", "Abort requested", None)
        return self.get_job(task_id)

    def abort_by_key(self, key: str) -> GenerationJob:
        with self._lock:
            task_id = self._key_to_task_id.get(key)
        if task_id is None:
            raise TaskNotFoundError(key)
        return self.abort(task_id)

    def is_abort_requested(self, task_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(task_id)
            return bool(job and job.abort_requested)

    def _create_job(
        self,
        task_type: str,
        request_payload: dict[str, Any],
        key: str | None,
        task_id: str | None = None,
    ) -> str:
        task_id = task_id or str(uuid4())
        job = GenerationJob(
            task_id=task_id,
            key=key,
            task_type=task_type,
            status=TaskStatus.QUEUED,
            request_payload=request_payload,
        )
        with self._lock:
            self._jobs[task_id] = job
            if key:
                self._key_to_task_id[key] = task_id
        self._publish(task_id, "queued", "queued", "Task queued", {"task_type": task_type, "key": key})
        return task_id

    def _reusable_task_id(
        self,
        key: str,
        request_payload: dict[str, Any] | None = None,
    ) -> str | None:
        """Collapse repeated clicks for the same tenant/story/scenario.

        Queued/running work is shared, and a completed result is replayed until
        its repository/story key changes. Failed or aborted work may be retried.
        """
        with self._lock:
            task_id = self._key_to_task_id.get(key)
            job = self._jobs.get(task_id) if task_id else None
            same_inputs = request_payload is None or job.request_payload == request_payload
            if job and same_inputs and job.status in {
                TaskStatus.QUEUED, TaskStatus.RUNNING, TaskStatus.COMPLETED
            }:
                log_step("api_generation_idempotent_replay", {"task_id": task_id, "key": key})
                return task_id
        return None

    def _run_scenario_generation(
        self,
        task_id: str,
        request: GenerateApiScenariosRequest,
        db: Any | None,
    ) -> None:
        self._run(task_id, lambda orchestrator: orchestrator.generate_scenarios(
            task_id=task_id,
            request=request,
            publish=lambda stage, message, payload=None: self._publish(
                task_id, "progress", stage, message, payload
            ),
            is_abort_requested=lambda: self.is_abort_requested(task_id),
        ), db)

    def _run_test_code_generation(
        self,
        task_id: str,
        request: GenerateApiTestCodeRequest,
        db: Any | None,
    ) -> None:
        self._run(task_id, lambda orchestrator: orchestrator.generate_test_code(
            task_id=task_id,
            request=request,
            publish=lambda stage, message, payload=None: self._publish(
                task_id, "progress", stage, message, payload
            ),
            is_abort_requested=lambda: self.is_abort_requested(task_id),
        ), db)

    def _run(self, task_id: str, work, db: Any | None) -> None:
        self._mark_running(task_id)
        try:
            orchestrator = GenerationOrchestrator(db=db)
            result = work(orchestrator)
            self._mark_completed(task_id, result.model_dump(mode="json"))
        except AbortRequestedError:
            self._mark_aborted(task_id)
        except Exception as exc:
            log_exception(exc, context={"task_id": task_id, "stage": "task_worker"})
            self._mark_failed(task_id, str(exc))

    def _mark_running(self, task_id: str) -> None:
        log_step("api_generation_task_running", {"task_id": task_id})
        with self._lock:
            job = self._require_job(task_id)
            job.status = TaskStatus.RUNNING
            job.stage = "running"
            job.touch()
        self._publish(task_id, "running", "running", "Task started", None)

    def _mark_completed(self, task_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            job = self._require_job(task_id)
            job.status = TaskStatus.COMPLETED
            job.stage = "completed"
            job.result = result
            job.touch()
        self._publish(task_id, "completed", "completed", "Task completed", result)

    def _mark_failed(self, task_id: str, error: str) -> None:
        with self._lock:
            job = self._require_job(task_id)
            job.status = TaskStatus.FAILED
            job.stage = "failed"
            job.error = error
            job.touch()
        self._publish(task_id, "failed", "failed", "Task failed", {"error": error})

    def _mark_aborted(self, task_id: str) -> None:
        with self._lock:
            job = self._require_job(task_id)
            job.status = TaskStatus.ABORTED
            job.stage = "aborted"
            job.abort_requested = True
            job.touch()
        self._publish(task_id, "aborted", "aborted", "Task aborted", None)

    def _publish(
        self,
        task_id: str,
        event_type: str,
        stage: str,
        message: str,
        payload: dict[str, Any] | None,
    ) -> None:
        sse_manager.publish(task_id, event_type, stage, message, payload)
        with self._lock:
            job = self._jobs.get(task_id)
            if job:
                job.stage = stage
                job.updated_at = datetime.now(timezone.utc)
                job.events = sse_manager.get_events(task_id)

    def _require_job(self, task_id: str) -> GenerationJob:
        job = self._jobs.get(task_id)
        if job is None:
            raise TaskNotFoundError(task_id)
        return job


def _require_resolved_repo_path(
    request: GenerateApiTestCodeRequest | GenerateApiTestsRequest,
) -> None:
    """The public contract resolves repo_path server-side (test_agent parity);
    by the time work is enqueued it must be concrete."""
    if not (request.repo_path or "").strip():
        raise ValueError(
            "repo_path was not resolved before enqueueing API test generation"
        )


task_manager = ApiTestGenerationTaskManager()


def make_api_test_key(
    tenant_id: int | str,
    user_story_hierarchy_id: int,
    testcase_id: str,
    row_id: int | str | None = None,
) -> str:
    return f"{tenant_id}:{user_story_hierarchy_id}:{testcase_id}:{row_id or 'default'}"


def make_api_scenario_key(
    tenant_id: int | str,
    user_story_hierarchy_id: int,
    user_story_id: str | None = None,
) -> str:
    return f"{tenant_id}:{user_story_hierarchy_id}:{user_story_id or 'story'}:api-scenarios"


def enqueue_api_scenario_generation_task(
    request: GenerateApiScenariosRequest,
    db: Any | None = None,
) -> str:
    return task_manager.enqueue_scenario_generation(request, db=db)


def enqueue_api_test_code_generation_task(
    request: GenerateApiTestCodeRequest,
    db: Any | None = None,
) -> str:
    return task_manager.enqueue_test_code_generation(request, db=db)


def enqueue_api_testgen_task(
    task_id: str | None,
    payload: dict[str, Any],
    db: Any | None = None,
) -> str:
    request = GenerateApiTestsRequest.model_validate(payload)
    return task_manager.enqueue_api_tests(request, db=db, task_id=task_id)


def enqueue_api_tests_task(
    request: GenerateApiTestsRequest,
    db: Any | None = None,
) -> str:
    return task_manager.enqueue_api_tests(request, db=db)


def get_api_generation_task_status(task_id: str) -> GenerationJob:
    return task_manager.get_job(task_id)


def get_api_generation_task_status_by_key(key: str) -> GenerationJob:
    return task_manager.get_job_by_key(key)


def abort_api_generation_task(task_id: str) -> GenerationJob:
    return task_manager.abort(task_id)


def abort_api_test_task(key: str) -> GenerationJob:
    return task_manager.abort_by_key(key)


def subscribe_api_test_status(key: str) -> list:
    return sse_manager.get_events(task_manager.get_job_by_key(key).task_id)


def unsubscribe_api_test_status(key: str, queue: Any | None = None) -> None:
    return None


def publish_api_test_status(key: str, event: dict[str, Any]) -> None:
    job = task_manager.get_job_by_key(key)
    sse_manager.publish(
        job.task_id,
        event.get("status", "progress"),
        event.get("stage", event.get("status", "progress")),
        event.get("message", "API test generation update"),
        event,
    )
