"""Agentic integration for the existing ScriptGen task-manager lifecycle.

This file intentionally contains only the new/refactored pieces. The existing
task manager remains the owner of queueing, DB status, SSE, heartbeat, abort,
execution details, terminal status, and cleanup for both generation modes.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Coroutine


def _normalize_worker_type(request_data_dict: dict[str, Any]) -> str:
    """Normalize all supported generation-mode inputs."""
    raw_worker_type = (
        request_data_dict.get("worker_type")
        or request_data_dict.get("execution_mode")
        or request_data_dict.get("generation_mode")
    )
    if raw_worker_type is None and request_data_dict.get("is_agentic") is True:
        raw_worker_type = "agentic"

    worker_type = str(raw_worker_type or "legacy").strip().lower()
    if worker_type not in {"legacy", "agentic"}:
        worker_type = "legacy"

    request_data_dict["worker_type"] = worker_type
    return worker_type


def normalize_enqueued_request(request_data_dict: dict[str, Any]) -> dict[str, Any]:
    """Prepare queue data without creating a second execution lifecycle."""
    normalized = dict(request_data_dict or {})
    _normalize_worker_type(normalized)

    job_id = str(normalized.get("job_id") or "").strip()
    if job_id:
        normalized["job_id"] = job_id
    else:
        normalized.pop("job_id", None)
    return normalized


async def _run_agentic_generation(
    *,
    user_story_hierarchy_id: Any,
    testcase_id: Any,
    request_data_dict: dict[str, Any],
    db: Any,
    abort_event: threading.Event,
    log_callback: Callable[..., None],
) -> dict[str, Any]:
    """Run only the agentic generation engine, with no lifecycle ownership."""
    from worktop.test_agent.app.adapters.script_gen_adapter import ScriptGenAdapter
    from worktop.test_agent.app.schemas.generation_request import GenerationRequest
    from worktop.test_agent.app.services.generation_orchestrator import (
        GenerationOrchestrator,
    )

    if abort_event.is_set():
        raise asyncio.CancelledError(
            "Task aborted before agentic generation started."
        )

    raw_generation_request = request_data_dict.get("generation_request")
    if not raw_generation_request:
        raise ValueError("generation_request is required for agentic generation")

    generation_request = GenerationRequest.model_validate(raw_generation_request)
    log_callback(
        "Agentic generation pipeline started",
        level="INFO",
        progress=0.05,
    )

    orchestrator = GenerationOrchestrator(db=db)
    generation_result = await asyncio.to_thread(
        orchestrator.generate,
        generation_request,
    )

    if abort_event.is_set():
        raise asyncio.CancelledError("Task aborted during agentic generation.")

    final_result = ScriptGenAdapter.to_response_dict(
        generation_result,
        flow_steps_count=int(request_data_dict.get("flow_steps_count", 0) or 0),
        automation_steps_count=int(
            request_data_dict.get("automation_steps_count", 0) or 0
        ),
    )
    if not isinstance(final_result, dict):
        raise TypeError("ScriptGenAdapter.to_response_dict() must return dict")

    log_callback(
        "Agentic code generation completed",
        level="INFO",
        progress=1.0,
    )
    return final_result


def select_generation_coroutine(
    *,
    user_story_hierarchy_id: Any,
    testcase_id: Any,
    request_data_dict: dict[str, Any],
    db: Any,
    abort_event: threading.Event,
    log_callback: Callable[..., None],
    legacy_coroutine_factory: Callable[[], Coroutine[Any, Any, Any]],
) -> Coroutine[Any, Any, Any]:
    """Select only the generation engine inside the shared execute function."""
    worker_type = _normalize_worker_type(request_data_dict)
    if worker_type == "agentic":
        log_callback(
            "Using agentic script generation",
            level="INFO",
            progress=0.02,
        )
        return _run_agentic_generation(
            user_story_hierarchy_id=user_story_hierarchy_id,
            testcase_id=testcase_id,
            request_data_dict=request_data_dict,
            db=db,
            abort_event=abort_event,
            log_callback=log_callback,
        )

    log_callback(
        "Using legacy script generation",
        level="INFO",
        progress=0.02,
    )
    return legacy_coroutine_factory()


def execute_worker_task(
    *,
    user_story_hierarchy_id: Any,
    testcase_id: Any,
    request_data_dict: dict[str, Any],
    shared_execute: Callable[[Any, Any, dict[str, Any]], None],
) -> None:
    """Worker entry point: always invoke the single shared lifecycle."""
    shared_execute(
        user_story_hierarchy_id,
        testcase_id,
        normalize_enqueued_request(request_data_dict),
    )


def _execute_agentic_scriptgen_task(
    user_story_hierarchy_id: Any,
    testcase_id: Any,
    request_data_dict: dict[str, Any],
    *,
    shared_execute: Callable[[Any, Any, dict[str, Any]], None],
) -> None:
    """Temporary compatibility wrapper for callers not yet migrated."""
    normalized_request = normalize_enqueued_request(request_data_dict)
    normalized_request["worker_type"] = "agentic"
    shared_execute(
        user_story_hierarchy_id,
        testcase_id,
        normalized_request,
    )
