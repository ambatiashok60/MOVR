"""
Compatibility runtime between the new test_agent generation API and the
existing Script Generator worker, queue, SSE and abort infrastructure.

This module intentionally isolates all imports from:

    worktop.script_generator

The new generation route should depend only on this runtime module rather
than importing the legacy task manager directly.
"""

from __future__ import annotations

from queue import Queue
from typing import Any, Callable

from worktop.test_agent.utils.logging import get_logger

logger = get_logger(__name__)


class RuntimeUnavailableError(RuntimeError):
    """Raised when the legacy Script Generator runtime is unavailable."""


def _task_manager() -> Any:
    """
    Import and return the existing Script Generator task-manager module.

    The import is delayed to:

    - avoid circular imports during FastAPI startup;
    - keep test_agent importable in isolated unit tests;
    - avoid forcing legacy worker dependencies into every process.
    """
    try:
        from worktop.script_generator.app.task_managers import (
            script_generation_task_manager,
        )

        return script_generation_task_manager

    except Exception as exc:
        raise RuntimeUnavailableError(
            "Legacy Script Generator task manager is unavailable."
        ) from exc


def _resolve_callable(
    module: Any,
    *candidate_names: str,
) -> Callable[..., Any] | None:
    """
    Return the first callable found on a module.

    This allows the adapter to tolerate minor naming differences between
    legacy task-manager versions.
    """
    for name in candidate_names:
        candidate = getattr(module, name, None)
        if callable(candidate):
            return candidate

    return None


def _resolve_queue(module: Any) -> Queue[Any] | Any | None:
    """
    Find the queue used by the legacy Script Generator worker.

    Known names are checked in order. Add another candidate here only when
    the legacy task manager uses a different exported queue name.
    """
    for name in (
        "scriptgen_queue",
        "script_generation_queue",
        "generation_queue",
        "task_queue",
    ):
        queue_object = getattr(module, name, None)
        if queue_object is not None and hasattr(queue_object, "put"):
            return queue_object

    return None


def start_scriptgen_worker() -> None:
    """
    Start the existing Script Generator worker.

    Safe to call repeatedly when the legacy worker implementation is already
    idempotent.
    """
    module = _task_manager()

    start_worker = _resolve_callable(
        module,
        "start_scriptgen_worker",
        "start_script_generation_worker",
    )

    if start_worker is None:
        raise RuntimeUnavailableError(
            "Legacy task manager does not expose a Script Generator "
            "worker-start function."
        )

    start_worker()

    logger.info("Legacy Script Generator worker start requested")


def stop_scriptgen_worker() -> None:
    """
    Stop the existing Script Generator worker.

    Failure during application shutdown is logged rather than propagated.
    """
    try:
        module = _task_manager()

        stop_worker = _resolve_callable(
            module,
            "stop_scriptgen_worker",
            "stop_script_generation_worker",
        )

        if stop_worker is None:
            logger.debug(
                "Legacy Script Generator task manager has no stop function"
            )
            return

        stop_worker()

        logger.info("Legacy Script Generator worker stop requested")

    except RuntimeUnavailableError:
        logger.debug(
            "Legacy Script Generator runtime is unavailable during shutdown"
        )

    except Exception:
        logger.exception("Failed to stop legacy Script Generator worker")


def enqueue_agent_generation_task(
    *,
    job_id: str,
    user_story_hierarchy_id: int,
    testcase_id: str,
    tenant_id: int,
    generation_request: dict[str, Any],
    user_story_id: str | None = None,
    row_id: int | str | None = None,
    requested_by: str | None = None,
) -> None:
    """
    Enqueue a Test Agent generation request on the existing Script Generator
    worker queue.

    The submitted task deliberately contains both:

    - identifiers expected by the legacy SSE/task-management layer;
    - the serialized GenerationRequest expected by the new orchestrator.

    If the legacy task manager exposes a public enqueue function, it is used.
    Otherwise, the request is placed directly on its exported queue.
    """
    module = _task_manager()

    task_payload: dict[str, Any] = {
        "task_type": "agent_generation",
        "job_id": str(job_id),
        "request_id": str(job_id),
        "user_story_hierarchy_id": int(user_story_hierarchy_id),
        "testcase_id": str(testcase_id),
        "test_case_id": str(testcase_id),
        "tenant_id": int(tenant_id),
        "generation_request": generation_request,
        "user_story_id": user_story_id,
        "row_id": row_id,
        "requested_by": requested_by,
    }

    enqueue_function = _resolve_callable(
        module,
        "enqueue_agent_generation_task",
        "enqueue_generation_task",
        "enqueue_script_generation_task",
        "submit_generation_task",
    )

    if enqueue_function is not None:
        try:
            enqueue_function(
                job_id=str(job_id),
                user_story_hierarchy_id=int(user_story_hierarchy_id),
                testcase_id=str(testcase_id),
                tenant_id=int(tenant_id),
                generation_request=generation_request,
                user_story_id=user_story_id,
                row_id=row_id,
                requested_by=requested_by,
            )

        except TypeError:
            # Compatibility fallback for older task managers that accept one
            # complete dictionary instead of keyword arguments.
            enqueue_function(task_payload)

        logger.info(
            "Generation task submitted through legacy enqueue function | "
            "job_id=%s hierarchy_id=%s testcase_id=%s tenant_id=%s",
            job_id,
            user_story_hierarchy_id,
            testcase_id,
            tenant_id,
        )
        return

    task_queue = _resolve_queue(module)

    if task_queue is None:
        raise RuntimeUnavailableError(
            "Legacy Script Generator task manager exposes neither a supported "
            "enqueue function nor a writable queue."
        )

    task_queue.put(task_payload)

    logger.info(
        "Generation task placed on legacy queue | "
        "job_id=%s hierarchy_id=%s testcase_id=%s tenant_id=%s",
        job_id,
        user_story_hierarchy_id,
        testcase_id,
        tenant_id,
    )


def make_key(
    *,
    user_story_hierarchy_id: int,
    testcase_id: str,
    tenant_id: int,
) -> Any:
    """
    Build the same subscriber key used by the legacy Script Generator SSE
    implementation.
    """
    module = _task_manager()

    key_builder = _resolve_callable(module, "make_key")

    if key_builder is None:
        return (
            str(user_story_hierarchy_id),
            str(testcase_id),
            str(tenant_id),
        )

    return key_builder(
        user_story_hierarchy_id,
        testcase_id,
        tenant_id,
    )


def subscribe_scriptgen_status(
    key: Any,
    queue: Any,
) -> None:
    """Subscribe a queue to legacy Script Generator status events."""
    module = _task_manager()

    subscribe = _resolve_callable(
        module,
        "subscribe_scriptgen_status",
        "subscribe_generation_status",
    )

    if subscribe is None:
        raise RuntimeUnavailableError(
            "Legacy task manager does not expose a status-subscribe function."
        )

    subscribe(key, queue)


def unsubscribe_scriptgen_status(
    key: Any,
    queue: Any,
) -> None:
    """Remove a queue from legacy Script Generator status subscriptions."""
    try:
        module = _task_manager()

        unsubscribe = _resolve_callable(
            module,
            "unsubscribe_scriptgen_status",
            "unsubscribe_generation_status",
        )

        if unsubscribe is None:
            return

        unsubscribe(key, queue)

    except RuntimeUnavailableError:
        return

    except Exception:
        logger.exception(
            "Failed to unsubscribe from Script Generator status | key=%s",
            key,
        )


def publish_scriptgen_status(
    *,
    user_story_hierarchy_id: int,
    testcase_id: str,
    tenant_id: int,
    payload: dict[str, Any] | str,
) -> None:
    """
    Publish a status event through the existing Script Generator SSE registry.
    """
    module = _task_manager()

    publisher = _resolve_callable(
        module,
        "publish_scriptgen_status",
        "publish_generation_status",
    )

    if publisher is None:
        raise RuntimeUnavailableError(
            "Legacy task manager does not expose a status-publish function."
        )

    try:
        publisher(
            user_story_hierarchy_id,
            testcase_id,
            payload,
            tenant_id=tenant_id,
        )

    except TypeError:
        publisher(
            user_story_hierarchy_id,
            testcase_id,
            payload,
            tenant_id,
        )


def build_sse_payload(
    *,
    status: str,
    job_id: str,
    user_story_hierarchy_id: int,
    testcase_id: str,
    user_story_id: str | None = None,
    row_id: int | str | None = None,
    progress: float | None = None,
    result: dict[str, Any] | None = None,
    error: dict[str, Any] | str | None = None,
    logs: list[dict[str, Any]] | None = None,
    is_final: bool = False,
) -> dict[str, Any]:
    """
    Build an SSE payload using the legacy helper when available.

    A compatible local payload is returned when the legacy module does not
    expose build_sse_payload.
    """
    module = _task_manager()

    builder = _resolve_callable(module, "build_sse_payload")

    if builder is not None:
        return builder(
            status=status,
            request_id=job_id,
            user_story_hierarchy_id=user_story_hierarchy_id,
            testcase_id=testcase_id,
            user_story_id=user_story_id,
            row_id=row_id,
            progress=progress,
            result=result,
            error=error,
            logs=logs,
            is_final=is_final,
        )

    payload: dict[str, Any] = {
        "v": 1,
        "type": "scriptgen_status",
        "status": status,
        "request_id": job_id,
        "job_id": job_id,
        "user_story_hierarchy_id": user_story_hierarchy_id,
        "testcase_id": testcase_id,
        "user_story_id": user_story_id,
        "row_id": row_id,
    }

    if progress is not None:
        payload["progress"] = progress

    if result is not None:
        payload["result"] = result

    if error is not None:
        payload["error"] = error

    if logs is not None:
        payload["logs"] = logs

    if is_final:
        payload["is_final"] = True

    return payload


def publish_generation_started(
    *,
    job_id: str,
    user_story_hierarchy_id: int,
    testcase_id: str,
    tenant_id: int,
    user_story_id: str | None = None,
    row_id: int | str | None = None,
) -> None:
    """Publish a generation-started event."""
    payload = build_sse_payload(
        status="InProgress",
        job_id=job_id,
        user_story_hierarchy_id=user_story_hierarchy_id,
        testcase_id=testcase_id,
        user_story_id=user_story_id,
        row_id=row_id,
        progress=0.0,
    )

    publish_scriptgen_status(
        user_story_hierarchy_id=user_story_hierarchy_id,
        testcase_id=testcase_id,
        tenant_id=tenant_id,
        payload=payload,
    )


def publish_generation_completed(
    *,
    job_id: str,
    user_story_hierarchy_id: int,
    testcase_id: str,
    tenant_id: int,
    result: dict[str, Any],
    user_story_id: str | None = None,
    row_id: int | str | None = None,
) -> None:
    """Publish the terminal Completed event."""
    payload = build_sse_payload(
        status="Completed",
        job_id=job_id,
        user_story_hierarchy_id=user_story_hierarchy_id,
        testcase_id=testcase_id,
        user_story_id=user_story_id,
        row_id=row_id,
        progress=1.0,
        result=result,
        is_final=True,
    )

    publish_scriptgen_status(
        user_story_hierarchy_id=user_story_hierarchy_id,
        testcase_id=testcase_id,
        tenant_id=tenant_id,
        payload=payload,
    )


def publish_generation_failed(
    *,
    job_id: str,
    user_story_hierarchy_id: int,
    testcase_id: str,
    tenant_id: int,
    error: str,
    user_story_id: str | None = None,
    row_id: int | str | None = None,
) -> None:
    """Publish the terminal Failed event."""
    payload = build_sse_payload(
        status="Failed",
        job_id=job_id,
        user_story_hierarchy_id=user_story_hierarchy_id,
        testcase_id=testcase_id,
        user_story_id=user_story_id,
        row_id=row_id,
        progress=1.0,
        error={
            "message": error,
            "job_id": job_id,
        },
        is_final=True,
    )

    publish_scriptgen_status(
        user_story_hierarchy_id=user_story_hierarchy_id,
        testcase_id=testcase_id,
        tenant_id=tenant_id,
        payload=payload,
    )


def abort_task(
    *,
    user_story_hierarchy_id: int,
    testcase_id: str,
    tenant_id: int,
    user_story_id: str | None = None,
    row_id: int | str | None = None,
) -> dict[str, Any]:
    """Delegate task abortion to the existing Script Generator runtime."""
    module = _task_manager()

    abort = _resolve_callable(module, "abort_task")

    if abort is None:
        raise RuntimeUnavailableError(
            "Legacy task manager does not expose an abort function."
        )

    return abort(
        user_story_hierarchy_id=user_story_hierarchy_id,
        testcase_id=testcase_id,
        tenant_id=tenant_id,
        user_story_id=user_story_id,
        row_id=row_id,
    )