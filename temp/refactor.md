from pathlib import Path

content = r'''"""
script_generation_task_manager_refactor_sketch.py

PURPOSE
-------
This is a migration sketch for refactoring the current ScriptGen task manager.

It is NOT intended to replace the production file line-for-line.
It shows:

    1. What can remain unchanged.
    2. What must be updated.
    3. What should be removed.
    4. Where the legacy and agentic generation branch should live.
    5. How to keep one shared lifecycle for:
       - DB status
       - SSE
       - logging
       - heartbeat
       - abort
       - execution details
       - terminal completion/failure
       - cleanup

IMPORTANT DESIGN RULE
---------------------
There must be only ONE task lifecycle:

    enqueue
        -> worker
        -> shared execute function
        -> legacy OR agentic generation
        -> shared persistence
        -> shared final SSE
        -> shared cleanup

Do NOT maintain two complete lifecycle implementations.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import threading
import time
from queue import Empty, Queue
from typing import Any, Callable, Coroutine


# =============================================================================
# KEEP AS-IS
# =============================================================================
# Keep the existing imports used by:
#
# - build_sse_payload
# - publish_scriptgen_status
# - TestCaseService
# - ExecutionDetails
# - db_session_context
# - logger
# - subscriber helpers
# - shared-steps helpers
# - abort handling
#
# Do not rewrite working helper implementations unless compilation proves
# their signatures differ from this sketch.


# =============================================================================
# EXISTING GLOBALS - KEEP AS-IS
# =============================================================================

KeyType = tuple[str, str, str]

MAX_LOGS = 200
TERMINAL_STATUSES = {"Completed", "Failed", "Aborted"}

scriptgen_queue: Queue = Queue()
scriptgen_stop_event = threading.Event()

SCRIPTGEN_MAIN_LOOP: asyncio.AbstractEventLoop | None = None
_SCRIPTGEN_LOOP_THREAD: threading.Thread | None = None
_SCRIPTGEN_WORKER_THREAD: threading.Thread | None = None

abort_signals: dict[KeyType, threading.Event] = {}
_ABORT_LOCK = threading.Lock()


# =============================================================================
# KEEP THESE EXISTING FUNCTIONS AS-IS
# =============================================================================
#
# def build_sse_payload(...):
#     ...
#
# def set_scriptgen_main_event_loop(...):
#     ...
#
# def make_key(...):
#     ...
#
# def abort_task(...):
#     ...
#
# def subscribe_scriptgen_status(...):
#     ...
#
# def unsubscribe_scriptgen_status(...):
#     ...
#
# def _safe_put_scriptgen_status(...):
#     ...
#
# def publish_scriptgen_status(...):
#     ...
#
# def cleanup_stale_subscribers(...):
#     ...
#
# def make_shared_steps_key(...):
#     ...
#
# def subscribe_shared_steps_status(...):
#     ...
#
# def unsubscribe_shared_steps_status(...):
#     ...
#
# def publish_shared_steps_status(...):
#     ...
#
# def build_shared_steps_payload(...):
#     ...
#
# def _open_db_session(...):
#     ...
#
# def db_session_context(...):
#     ...
#
# def ensure_worker_started(...):
#     ...
#
# def stop_scriptgen_worker(...):
#     ...
#
# Keep these helpers untouched because they already work for the legacy flow.


# =============================================================================
# SMALL HELPER TO ADD
# =============================================================================

def _normalize_worker_type(request_data_dict: dict[str, Any]) -> str:
    """
    NEW HELPER.

    Normalize all possible mode fields into one supported field.

    Accepted output:
        "legacy"
        "agentic"

    This avoids mismatches such as:
        worker_type
        execution_mode
        generation_mode
        is_agentic
    """

    raw_worker_type = (
        request_data_dict.get("worker_type")
        or request_data_dict.get("execution_mode")
        or request_data_dict.get("generation_mode")
    )

    if raw_worker_type is None and request_data_dict.get("is_agentic") is True:
        raw_worker_type = "agentic"

    worker_type = str(raw_worker_type or "legacy").strip().lower()

    if worker_type not in {"legacy", "agentic"}:
        # REPLACE logger.warning with your existing custom logger call.
        # logger.warning(
        #     "[SCRIPTGEN] Unsupported worker_type=%s; using legacy",
        #     worker_type,
        # )
        worker_type = "legacy"

    request_data_dict["worker_type"] = worker_type
    return worker_type


# =============================================================================
# UPDATE THIS FUNCTION: enqueue_scriptgen_task
# =============================================================================

def enqueue_scriptgen_task(
    row: Any,
    request_data_dict: dict[str, Any],
) -> None:
    """
    UPDATE EXISTING FUNCTION, DO NOT REWRITE THE REST UNNECESSARILY.

    KEEP:
        - identifier extraction
        - row_id enrichment
        - DB update to Inprogress
        - stale replay-buffer cleanup
        - stale abort-signal cleanup
        - ensure_worker_started()
        - queue.put(...)
        - initial SSE publication
        - existing logging

    ADD:
        - worker type normalization
        - job_id normalization

    DO NOT:
        - branch to legacy or agentic here
        - call agentic orchestrator here
        - create a second queue
    """

    # KEEP EXISTING IDENTIFIER EXTRACTION.
    user_story_hierarchy_id = (
        request_data_dict.get("user_story_hierarchy_id")
        or getattr(row, "user_story_hierarchy_id", None)
    )
    testcase_id = (
        request_data_dict.get("testcase_id")
        or getattr(row, "testcase_id", None)
    )
    row_id = request_data_dict.get("row_id") or getattr(row, "row_id", None)

    if user_story_hierarchy_id is None or testcase_id is None:
        # KEEP existing logger/error behavior.
        return

    request_data_dict = dict(request_data_dict or {})

    if row_id is not None and "row_id" not in request_data_dict:
        request_data_dict["row_id"] = row_id

    # -------------------------------------------------------------------------
    # ADD THIS
    # -------------------------------------------------------------------------
    _normalize_worker_type(request_data_dict)

    job_id = str(request_data_dict.get("job_id") or "").strip()
    if job_id:
        request_data_dict["job_id"] = job_id
    else:
        request_data_dict.pop("job_id", None)

    # -------------------------------------------------------------------------
    # KEEP EXISTING DB UPDATE
    # -------------------------------------------------------------------------
    # with db_session_context() as db:
    #     TestCaseService.script_generation_status(
    #         db,
    #         str(user_story_hierarchy_id),
    #         testcase_id,
    #         "Inprogress",
    #     )
    #     db.commit()

    # -------------------------------------------------------------------------
    # KEEP EXISTING REPLAY/ABORT CLEANUP
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # KEEP
    # -------------------------------------------------------------------------
    # ensure_worker_started()

    # -------------------------------------------------------------------------
    # KEEP SAME QUEUE TUPLE
    # -------------------------------------------------------------------------
    scriptgen_queue.put(
        (
            user_story_hierarchy_id,
            testcase_id,
            request_data_dict,
        )
    )

    # -------------------------------------------------------------------------
    # KEEP EXISTING INITIAL SSE
    # -------------------------------------------------------------------------
    # NOTE:
    # Your current implementation publishes a queued message with status
    # "Inprogress". Since the legacy UI already works with that contract,
    # keep it unchanged for now.
    #
    # publish_scriptgen_status(
    #     user_story_hierarchy_id,
    #     testcase_id,
    #     build_sse_payload(
    #         status="Inprogress",
    #         log={...},
    #         log_index=0,
    #         progress=0.0,
    #         ...
    #     ),
    #     tenant_id=tenant_id,
    # )


# =============================================================================
# UPDATE THIS FUNCTION: scriptgen_worker
# =============================================================================

def scriptgen_worker() -> None:
    """
    UPDATED WORKER.

    MAIN CHANGE:
        REMOVE the branch that calls two full lifecycle functions.

    REMOVE THIS:

        worker_type = ...
        if worker_type == "agentic":
            _execute_agentic_scriptgen_task(...)
        else:
            _execute_scriptgen_task(...)

    REPLACE WITH:

        _execute_scriptgen_task(...)

    The shared execute function decides only which generation engine to call.
    """

    global SCRIPTGEN_MAIN_LOOP, _SCRIPTGEN_LOOP_THREAD

    scriptgen_stop_event.clear()

    SCRIPTGEN_MAIN_LOOP = asyncio.new_event_loop()
    asyncio.set_event_loop(SCRIPTGEN_MAIN_LOOP)

    _SCRIPTGEN_LOOP_THREAD = threading.Thread(
        target=SCRIPTGEN_MAIN_LOOP.run_forever,
        daemon=True,
    )
    _SCRIPTGEN_LOOP_THREAD.start()

    # logger.info("[SCRIPTGEN WORKER] Loop started.")

    cleanup_counter = 0

    while not scriptgen_stop_event.is_set():
        try:
            task = scriptgen_queue.get(timeout=1)
        except Empty:
            cleanup_counter += 1
            if cleanup_counter >= 60:
                cleanup_counter = 0
                # KEEP existing cleanup helper.
                # cleanup_stale_subscribers()
                pass
            continue

        if task is None:
            scriptgen_queue.task_done()
            break

        (
            user_story_hierarchy_id,
            testcase_id,
            request_data_dict,
        ) = task

        tenant_id = int(request_data_dict.get("tenant_id", 1) or 1)

        # ---------------------------------------------------------------------
        # KEEP EXISTING QUEUED-ABORT CHECK
        # ---------------------------------------------------------------------
        abort_key = (
            str(user_story_hierarchy_id),
            str(testcase_id),
            str(tenant_id),
        )

        with _ABORT_LOCK:
            abort_event = abort_signals.get(abort_key)

            if abort_event and abort_event.is_set():
                abort_signals.pop(abort_key, None)

                # KEEP existing DB update to Aborted.
                #
                # KEEP existing terminal Aborted SSE.
                #
                # IMPORTANT:
                # Do not call task_done() here and again in finally.
                # Either:
                #   - continue and let finally call task_done()
                # or:
                #   - call task_done() here and avoid finally.
                #
                # Recommended:
                # continue and allow finally below to call task_done() once.
                continue

        try:
            # -----------------------------------------------------------------
            # SINGLE SHARED LIFECYCLE ENTRY POINT
            # -----------------------------------------------------------------
            _execute_scriptgen_task(
                user_story_hierarchy_id,
                testcase_id,
                request_data_dict,
            )

        except Exception as exc:
            # -----------------------------------------------------------------
            # DEFENSIVE FALLBACK ONLY
            # -----------------------------------------------------------------
            # Normally _execute_scriptgen_task handles terminal failure itself.
            #
            # KEEP a final worker-level fallback because the worker must never
            # leave the DB at Inprogress if an unexpected exception escapes.
            # -----------------------------------------------------------------

            # logger.exception(
            #     "[SCRIPTGEN WORKER] Unhandled task exception"
            # )

            # ADD fallback DB status update using a fresh session.
            #
            # try:
            #     with db_session_context() as failure_db:
            #         TestCaseService.script_generation_status(
            #             failure_db,
            #             str(user_story_hierarchy_id),
            #             testcase_id,
            #             "Failed",
            #         )
            #         failure_db.commit()
            # except Exception:
            #     logger.exception(...)

            # ADD fallback terminal SSE.
            #
            # try:
            #     publish_scriptgen_status(
            #         user_story_hierarchy_id,
            #         testcase_id,
            #         build_sse_payload(
            #             status="Failed",
            #             logs=[...],
            #             is_final=True,
            #             error={"message": str(exc)},
            #             progress=0.0,
            #             ...
            #         ),
            #         tenant_id=tenant_id,
            #     )
            # except Exception:
            #     logger.exception(...)

            raise

        finally:
            # IMPORTANT:
            # Exactly once per queue item.
            scriptgen_queue.task_done()

    # logger.info("[SCRIPTGEN WORKER] Exiting worker loop")


# =============================================================================
# ADD THIS FUNCTION: thin agentic generation runner
# =============================================================================

async def _run_agentic_generation(
    *,
    user_story_hierarchy_id: Any,
    testcase_id: Any,
    request_data_dict: dict[str, Any],
    db: Any,
    abort_event: threading.Event,
    log_callback: Callable[..., None],
) -> dict[str, Any]:
    """
    NEW FUNCTION.

    This function owns ONLY agentic generation.

    IT MAY:
        - validate GenerationRequest
        - instantiate GenerationOrchestrator
        - call orchestrator.generate(...)
        - adapt the result with ScriptGenAdapter
        - return dict result
        - raise exception

    IT MUST NOT:
        - update TestCaseService status
        - publish ScriptGen SSE
        - create ExecutionDetails
        - commit or rollback shared lifecycle DB work
        - manage ScriptGen replay buffers
        - manage ScriptGen terminal cleanup
        - own heartbeat
        - own final status
        - own generation_job_store as the UI source of truth
    """

    # KEEP imports inside function if they currently prevent circular imports.
    from worktop.test_agent.app.adapters.script_gen_adapter import (
        ScriptGenAdapter,
    )
    from worktop.test_agent.app.schemas.generation_request import (
        GenerationRequest,
    )
    from worktop.test_agent.app.services.generation_orchestrator import (
        GenerationOrchestrator,
    )

    if abort_event.is_set():
        raise asyncio.CancelledError(
            "Task aborted before agentic generation started."
        )

    raw_generation_request = request_data_dict.get("generation_request")

    if not raw_generation_request:
        raise ValueError(
            "generation_request is required for agentic generation"
        )

    generation_request = GenerationRequest.model_validate(
        raw_generation_request
    )

    log_callback(
        "Agentic generation pipeline started",
        level="INFO",
        progress=0.05,
    )

    orchestrator = GenerationOrchestrator(db=db)

    # KEEP asyncio.to_thread only if orchestrator.generate is synchronous.
    generation_result = await asyncio.to_thread(
        orchestrator.generate,
        generation_request,
    )

    if abort_event.is_set():
        raise asyncio.CancelledError(
            "Task aborted during agentic generation."
        )

    final_result = ScriptGenAdapter.to_response_dict(
        generation_result,
        flow_steps_count=int(
            request_data_dict.get("flow_steps_count", 0) or 0
        ),
        automation_steps_count=int(
            request_data_dict.get("automation_steps_count", 0) or 0
        ),
    )

    if not isinstance(final_result, dict):
        raise TypeError(
            "ScriptGenAdapter.to_response_dict() must return dict"
        )

    log_callback(
        "Agentic code generation completed",
        level="INFO",
        progress=1.0,
    )

    return final_result


# =============================================================================
# KEEP THIS FUNCTION AS THE SINGLE LIFECYCLE OWNER
# UPDATE ONLY THE GENERATION BRANCH
# =============================================================================

def _execute_scriptgen_task(
    user_story_hierarchy_id: Any,
    testcase_id: Any,
    request_data_dict: dict[str, Any],
) -> None:
    """
    KEEP THE EXISTING LEGACY FUNCTION AS THE MAIN EXECUTION FUNCTION.

    KEEP ALL EXISTING WORKING LOGIC FOR:
        - task start logging
        - tenant/user_story/row/testcase extraction
        - abort key creation
        - abort event creation
        - DB session creation
        - log_callback
        - initial Inprogress SSE
        - repo/config/browser/auth setup
        - telemetry wrapper
        - polling
        - heartbeat
        - abort
        - exception -> Failed
        - DB status update
        - ExecutionDetails persistence
        - final SSE payload
        - cleanup
        - abort signal removal
        - DB session close

    CHANGE ONLY:
        the section that currently creates the legacy generation coroutine.
    """

    if SCRIPTGEN_MAIN_LOOP is None:
        raise RuntimeError("SCRIPTGEN_MAIN_LOOP is not initialized")

    task_started_at = time.time()

    tenant_id = int(request_data_dict.get("tenant_id", 1) or 1)
    user_story_id = request_data_dict.get("user_story_id")
    row_id = request_data_dict.get("row_id")

    abort_key = (
        str(user_story_hierarchy_id),
        str(testcase_id),
        str(tenant_id),
    )

    with _ABORT_LOCK:
        abort_event = abort_signals.get(abort_key)
        if abort_event is None:
            abort_event = threading.Event()
            abort_signals[abort_key] = abort_event

    db_gen = None
    db = None

    logs: list[dict[str, Any]] = []
    log_counter = [1]
    current_progress = [0.0]

    def log_callback(
        message: str,
        level: str = "INFO",
        extra: dict[str, Any] | None = None,
        progress: float | None = None,
    ) -> None:
        """
        KEEP YOUR EXISTING IMPLEMENTATION.

        It should:
            - create one immutable log entry
            - append to logs
            - increment log_index
            - update current_progress
            - cap logs at MAX_LOGS
            - publish Inprogress delta SSE
        """

        entry: dict[str, Any] = {
            "message": message,
            "level": level,
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
        }

        if extra:
            entry.update(extra)

        logs.append(entry)

        if progress is not None:
            current_progress[0] = progress

        if len(logs) > MAX_LOGS:
            del logs[0]

        # KEEP existing publish_scriptgen_status(...) call here.

    try:
        # KEEP existing DB open logic.
        #
        # db_gen, db = _open_db_session()

        # KEEP existing initial status SSE.

        # KEEP existing repo path/config/browser/auth/service setup.
        #
        # script_gen_service = ScriptGenService(...)

        # ---------------------------------------------------------------------
        # ONLY GENERATION BRANCH SHOULD DIFFER
        # ---------------------------------------------------------------------
        worker_type = _normalize_worker_type(request_data_dict)

        if worker_type == "agentic":
            log_callback(
                "Using agentic script generation",
                level="INFO",
                progress=0.02,
            )

            coro: Coroutine[Any, Any, Any] = _run_agentic_generation(
                user_story_hierarchy_id=user_story_hierarchy_id,
                testcase_id=testcase_id,
                request_data_dict=request_data_dict,
                db=db,
                abort_event=abort_event,
                log_callback=log_callback,
            )

        else:
            log_callback(
                "Using legacy script generation",
                level="INFO",
                progress=0.02,
            )

            # KEEP your real existing legacy call exactly as-is.
            #
            # coro = script_gen_service.generate_automation_script(
            #     testcase_steps=request_data_dict.get("testcase_steps", []),
            #     test_data=request_data_dict.get("test_data", {}),
            #     testcase_name=request_data_dict.get("testcase_name", ""),
            #     headless=ds_headless,
            #     data_config=request_data_dict.get("data_config", True),
            #     additional_context=request_data_dict.get(
            #         "additional_context"
            #     ),
            #     pom_required=request_data_dict.get("pom_required", True),
            #     user_story_id=request_data_dict.get("user_story_id"),
            #     abort_event=abort_event,
            #     log_callback=log_callback,
            #     transformation_metadata=request_data_dict.get(
            #         "transformation_metadata"
            #     ),
            # )
            #
            # This placeholder exists only so this sketch parses.
            async def _legacy_placeholder() -> dict[str, Any]:
                raise NotImplementedError(
                    "Replace with existing generate_automation_script call"
                )

            coro = _legacy_placeholder()

        # ---------------------------------------------------------------------
        # KEEP EVERYTHING BELOW SHARED
        # ---------------------------------------------------------------------
        future = asyncio.run_coroutine_threadsafe(
            coro,
            SCRIPTGEN_MAIN_LOOP,
        )

        scriptgen_status = "Failed"
        final_result: Any = None

        heartbeat_interval = 15
        last_heartbeat = time.time()

        while True:
            try:
                final_result = future.result(timeout=0.2)
                scriptgen_status = "Completed"
                break

            except asyncio.CancelledError:
                scriptgen_status = "Aborted"
                final_result = None
                log_callback(
                    "Script generation was cancelled",
                    level="WARNING",
                )
                break

            except TimeoutError:
                if abort_event.is_set():
                    future.cancel()

                    with contextlib.suppress(Exception):
                        future.result(timeout=0.2)

                    scriptgen_status = "Aborted"
                    final_result = None

                    log_callback(
                        "Script generation was cancelled by user",
                        level="WARNING",
                    )
                    break

                now = time.time()
                if now - last_heartbeat >= heartbeat_interval:
                    last_heartbeat = now
                    log_callback(
                        "Still working...",
                        level="INFO",
                        progress=(
                            current_progress[0]
                            if current_progress[0] > 0
                            else None
                        ),
                    )

            except Exception as exc:
                scriptgen_status = "Failed"
                final_result = exc

                log_callback(
                    "Script generation encountered an error",
                    level="ERROR",
                )

                # KEEP existing detailed logger.exception(...)
                break

        # ---------------------------------------------------------------------
        # KEEP SHARED FINAL DB STATUS
        # ---------------------------------------------------------------------
        # try:
        #     TestCaseService.script_generation_status(
        #         db,
        #         str(user_story_hierarchy_id),
        #         testcase_id,
        #         scriptgen_status,
        #     )
        #     db.commit()
        # except Exception:
        #     with contextlib.suppress(Exception):
        #         db.rollback()
        #     logger.exception(...)

        # ---------------------------------------------------------------------
        # KEEP SHARED EXECUTION DETAILS PERSISTENCE
        # ---------------------------------------------------------------------
        # Use the existing ExecutionDetails model.
        #
        # ADD rollback on failure.
        #
        # script_path should prefer:
        #   1. details_dict["script_path"]
        #   2. details_dict["generated_spec_path"]
        #   3. first .spec.ts / .test.ts file
        # Do not blindly use files_changed[0].

        # ---------------------------------------------------------------------
        # OPTIONAL JOB STORE SYNC
        # ---------------------------------------------------------------------
        # generation_job_store must NOT be the UI source of truth.
        #
        # If retained, call it only after shared status is known.
        #
        # IMPORTANT:
        # Match the REAL function signatures from generation_job_store.py.
        #
        # Example only:
        #
        # if job_id:
        #     if scriptgen_status == "Completed":
        #         generation_job_store.complete(job_id, final_result)
        #     elif scriptgen_status == "Aborted":
        #         generation_job_store.abort(job_id)
        #     else:
        #         generation_job_store.fail(job_id, final_result)

        # ---------------------------------------------------------------------
        # KEEP SHARED FINAL SSE
        # ---------------------------------------------------------------------
        final_error = None

        if scriptgen_status == "Failed":
            error_message = "Unknown error"

            if isinstance(final_result, Exception):
                error_message = str(final_result)
            elif isinstance(final_result, dict):
                error_message = str(
                    final_result.get("error_message")
                    or error_message
                )

            final_error = {"message": error_message}

        # KEEP your existing build_sse_payload(...) and
        # publish_scriptgen_status(...) implementation.
        #
        # final_payload = build_sse_payload(
        #     status=scriptgen_status,
        #     logs=logs.copy(),
        #     is_final=True,
        #     result=(
        #         final_result
        #         if scriptgen_status == "Completed"
        #         else None
        #     ),
        #     error=final_error,
        #     progress=(
        #         1.0
        #         if scriptgen_status == "Completed"
        #         else 0.0
        #         if scriptgen_status == "Aborted"
        #         else 0.0
        #     ),
        #     user_story_id=user_story_id,
        #     row_id=row_id,
        #     testcase_id=testcase_id,
        #     user_story_hierarchy_id=user_story_hierarchy_id,
        # )
        #
        # publish_scriptgen_status(
        #     user_story_hierarchy_id,
        #     testcase_id,
        #     final_payload,
        #     tenant_id=tenant_id,
        # )

        elapsed = time.time() - task_started_at

        # KEEP existing final logger.info(...)

    except Exception as exc:
        # ---------------------------------------------------------------------
        # OUTERMOST SHARED FAILURE FALLBACK
        # ---------------------------------------------------------------------
        # This is required so malformed agentic requests do not leave DB status
        # at Inprogress.
        # ---------------------------------------------------------------------

        # logger.exception(
        #     "[SCRIPTGEN] Unhandled execution failure"
        # )

        # IMPORTANT:
        # Use a fresh DB session if the current session may be poisoned.
        #
        # try:
        #     with db_session_context() as failure_db:
        #         TestCaseService.script_generation_status(
        #             failure_db,
        #             str(user_story_hierarchy_id),
        #             testcase_id,
        #             "Failed",
        #         )
        #         failure_db.commit()
        # except Exception:
        #     logger.exception(...)

        # Publish final Failed SSE.
        #
        # with contextlib.suppress(Exception):
        #     publish_scriptgen_status(
        #         user_story_hierarchy_id,
        #         testcase_id,
        #         build_sse_payload(
        #             status="Failed",
        #             logs=logs.copy(),
        #             is_final=True,
        #             error={"message": str(exc)},
        #             progress=0.0,
        #             user_story_id=user_story_id,
        #             row_id=row_id,
        #             testcase_id=testcase_id,
        #             user_story_hierarchy_id=user_story_hierarchy_id,
        #         ),
        #         tenant_id=tenant_id,
        #     )

        raise

    finally:
        # KEEP existing DB generator/session cleanup.
        #
        # if db_gen:
        #     ...
        #
        # if hasattr(db_gen, "close"):
        #     ...

        with _ABORT_LOCK:
            abort_signals.pop(abort_key, None)


# =============================================================================
# REMOVE THIS FUNCTION BODY
# =============================================================================

def _execute_agentic_scriptgen_task(
    user_story_hierarchy_id: Any,
    testcase_id: Any,
    request_data_dict: dict[str, Any],
) -> None:
    """
    REMOVE THE CURRENT ~500-LINE DUPLICATED AGENTIC LIFECYCLE.

    REMOVE FROM THIS FUNCTION:
        - DB session creation
        - log_callback implementation
        - initial Inprogress SSE
        - heartbeat loop
        - abort loop
        - TestCaseService status updates
        - ExecutionDetails persistence
        - final SSE
        - generation_job_store terminal status ownership
        - cleanup
        - duplicated exception handling

    TEMPORARY COMPATIBILITY WRAPPER:
        Keep only this thin wrapper until all direct callers are migrated.
    """

    normalized_request = dict(request_data_dict or {})
    normalized_request["worker_type"] = "agentic"

    _execute_scriptgen_task(
        user_story_hierarchy_id,
        testcase_id,
        normalized_request,
    )


# =============================================================================
# DELETE AFTER CALLERS ARE MIGRATED
# =============================================================================
#
# Once scriptgen_worker and any route/controller no longer call
# _execute_agentic_scriptgen_task directly, delete the wrapper above entirely.
#
# Final state:
#
#     enqueue_scriptgen_task
#         -> scriptgen_worker
#             -> _execute_scriptgen_task
#                 -> legacy generate_automation_script
#                 OR
#                 -> _run_agentic_generation
#
# There should not be two separate lifecycle functions.


# =============================================================================
# REMOVE / CHANGE CHECKLIST
# =============================================================================
#
# REMOVE
# ------
# 1. Worker branch:
#
#       if worker_type == "agentic":
#           _execute_agentic_scriptgen_task(...)
#       else:
#           _execute_scriptgen_task(...)
#
# 2. Large duplicated _execute_agentic_scriptgen_task implementation.
#
# 3. Agentic-only copies of:
#       - log_callback
#       - heartbeat
#       - final DB status
#       - final SSE
#       - ExecutionDetails persistence
#       - abort cleanup
#
# 4. Job-store usage as the authoritative UI status.
#
# 5. Calls with incorrect keyword arguments, such as:
#
#       generation_job_store.complete(
#           job_id=job_id,
#           final_result=final_result,
#       )
#
#    unless those exact keywords match the real method signatures.
#
#
# CHANGE
# ------
# 1. Normalize worker_type in enqueue.
#
# 2. Worker always calls _execute_scriptgen_task.
#
# 3. Add _run_agentic_generation.
#
# 4. Add branch only around generation coroutine creation.
#
# 5. Add db.rollback() after failed DB operations.
#
# 6. Add outermost fallback Failed DB update using a fresh session.
#
# 7. Ensure terminal Failed SSE always has:
#       is_final=True
#       error={"message": "..."}
#       progress=0.0
#
# 8. Prefer explicit script_path instead of files_changed[0].
#
# 9. Ensure queue.task_done() is called exactly once.
#
#
# KEEP
# ----
# 1. SSE helpers.
# 2. Subscriber registries.
# 3. Shared-step streaming helpers.
# 4. Abort signal infrastructure.
# 5. Queue structure.
# 6. DB session helpers.
# 7. Existing legacy ScriptGen service setup.
# 8. Existing legacy lifecycle behavior.
# 9. Existing payload field names and status casing:
#       Inprogress
#       Completed
#       Failed
#       Aborted
#
#
# TEST AFTER REFACTOR
# -------------------
# 1. Legacy success
# 2. Legacy failure
# 3. Legacy abort
# 4. Agentic success
# 5. Agentic validation failure
# 6. Agentic orchestrator failure
# 7. Agentic abort
# 8. SSE subscriber reconnect
# 9. Browser refresh after completion
# 10. Missing job_id
# 11. Missing generation_request
# 12. DB commit failure
# 13. Final SSE publish failure
# 14. queue.task_done() balance
# 15. Status casing consistency
'''

path = Path("/mnt/data/script_generation_task_manager_refactor_sketch.py")
path.write_text(content, encoding="utf-8")
print(path)
