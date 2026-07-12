"""Thin boundary over the external script-generation task-manager runtime.

The queue, worker thread, asyncio loop, SSE publisher/replay and abort registry
live in the Worktop platform
(``worktop.script_generator.app.task_managers.*``), which is only importable
when this package is deployed into that platform. Routing all access through
this module keeps the API package importable and unit-testable standalone
(tests monkeypatch these functions), and gives the routes a single, stable
"public runtime API" to depend on rather than concrete globals.

Every function lazily imports the platform module and raises a clear
``RuntimeUnavailableError`` if it is absent, so a misconfigured deployment
fails loudly instead of silently.
"""

from __future__ import annotations

from typing import Any

from worktop.core_services.app.utility.custom_logger.logging import logger



class RuntimeUnavailableError(RuntimeError):
    """Raised when the platform task-manager runtime is not importable."""


def _task_manager() -> Any:
    try:
        from worktop.script_generator.app.task_managers import (
            script_generation_task_manager as task_manager,
        )
    except Exception as exc:  # pragma: no cover - exercised only off-platform
        raise RuntimeUnavailableError(
            "script generation task manager is not available in this deployment"
        ) from exc
    return task_manager


def enqueue_agent_generation_task(
    *,
    job_id: str,
    user_story_hierarchy_id: int,
    testcase_id: str,
    tenant_id: int,
    generation_request: dict[str, Any],
    user_story_id: str | None = None,
    row_id: int | None = None,
) -> None:
    """Enqueue an agent-generation task on the existing worker queue.

    The DB session is intentionally NOT passed: the worker opens its own.
    """
    _task_manager().enqueue_agent_generation_task(
        job_id=job_id,
        user_story_hierarchy_id=user_story_hierarchy_id,
        testcase_id=testcase_id,
        tenant_id=tenant_id,
        generation_request=generation_request,
        user_story_id=user_story_id,
        row_id=row_id,
    )


def abort_task(
    *,
    user_story_hierarchy_id: int,
    testcase_id: str,
    tenant_id: int,
    user_story_id: str | None = None,
    row_id: int | None = None,
) -> dict[str, Any]:
    return _task_manager().abort_task(
        user_story_hierarchy_id=user_story_hierarchy_id,
        testcase_id=testcase_id,
        tenant_id=tenant_id,
        user_story_id=user_story_id,
        row_id=row_id,
    )


def make_key(
    user_story_hierarchy_id: int, testcase_id: str, tenant_id: int
) -> Any:
    return _task_manager().make_key(
        user_story_hierarchy_id, testcase_id, tenant_id
    )


def subscribe_scriptgen_status(key: Any, queue: Any) -> None:
    _task_manager().subscribe_scriptgen_status(key, queue)


def generation_status_event_generator(**kwargs: Any) -> Any:
    """Return the shared production SSE generator (async iterator)."""
    try:
        from worktop.script_generator.app.task_managers.generation_status_stream import (  # noqa: E501
            generation_status_event_generator as generator,
        )
    except Exception as exc:  # pragma: no cover - exercised only off-platform
        raise RuntimeUnavailableError(
            "generation status stream is not available in this deployment"
        ) from exc
    return generator(**kwargs)


def stop_scriptgen_worker() -> None:
    """Best-effort worker shutdown; safe to call when the runtime is absent."""
    try:
        _task_manager().stop_scriptgen_worker()
    except RuntimeUnavailableError:
        logger.debug("script generation worker not present; nothing to stop")
    except Exception:
        logger.exception("Failed to stop script generation worker")
