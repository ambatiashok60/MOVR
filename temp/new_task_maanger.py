try:
    worker_type = str(
        request_data_dict.get(
            "worker_type",
            "legacy",
        )
    ).strip().lower()

    if worker_type == "agentic":
        _execute_agentic_scriptgen_task(
            user_story_hierarchy_id,
            testcase_id,
            request_data_dict,
        )
    else:
        # Existing legacy logic remains completely untouched.
        _execute_scriptgen_task(
            user_story_hierarchy_id,
            testcase_id,
            request_data_dict,
        )





def _execute_agentic_scriptgen_task(
    user_story_hierarchy_id: Any,
    testcase_id: Any,
    request_data_dict: dict[str, Any],
) -> None:
    """
    Execute the new GenerationOrchestrator while reusing the existing
    ScriptGen status, SSE, abort and execution-details infrastructure.

    The legacy _execute_scriptgen_task() is not modified.
    """

    import concurrent.futures

    from worktop.test_agent.app.adapters.script_gen_adapter import (
        ScriptGenAdapter,
    )
    from worktop.test_agent.app.schemas.generation_request import (
        GenerationRequest,
    )
    from worktop.test_agent.app.services.generation_job_store import (
        generation_job_store,
    )
    from worktop.test_agent.app.services.generation_orchestrator import (
        GenerationOrchestrator,
    )

    task_started_at = time.time()

    tenant_id = int(
        request_data_dict.get(
            "tenant_id",
            1,
        )
        or 1
    )

    job_id = str(
        request_data_dict.get(
            "job_id",
            "",
        )
    )

    user_story_id = request_data_dict.get(
        "user_story_id"
    )
    row_id = request_data_dict.get("row_id")

    abort_key = make_key(
        user_story_hierarchy_id,
        testcase_id,
        tenant_id,
    )

    db_gen = None
    db = None

    logs: list[dict[str, Any]] = []
    log_counter = [1]
    current_progress = [0.0]

    # --------------------------------------------------------------
    # Reuse the same abort-signal infrastructure.
    # --------------------------------------------------------------
    with _ABORT_LOCK:
        abort_event = abort_signals.get(abort_key)

        if abort_event is None:
            abort_event = threading.Event()
            abort_signals[abort_key] = abort_event

    try:
        db_gen, db = _open_db_session()

        def log_callback(
            message: str,
            level: str = "INFO",
            extra: dict[str, Any] | None = None,
            progress: float | None = None,
        ) -> None:
            entry: dict[str, Any] = {
                "message": message,
                "level": level,
                "ts": (
                    datetime.datetime.utcnow().isoformat()
                    + "Z"
                ),
            }

            if extra:
                entry.update(extra)

            logs.append(entry)

            log_index = log_counter[0]
            log_counter[0] += 1

            if progress is not None:
                current_progress[0] = progress

            if len(logs) > MAX_LOGS:
                del logs[0]

            publish_scriptgen_status(
                user_story_hierarchy_id,
                testcase_id,
                build_sse_payload(
                    status="Inprogress",
                    log=entry,
                    log_index=log_index,
                    progress=(
                        current_progress[0]
                        if current_progress[0] > 0
                        else None
                    ),
                    user_story_id=user_story_id,
                    row_id=row_id,
                    testcase_id=testcase_id,
                    user_story_hierarchy_id=(
                        user_story_hierarchy_id
                    ),
                ),
                tenant_id=tenant_id,
            )

        # ----------------------------------------------------------
        # Same initial running status.
        # ----------------------------------------------------------
        start_entry = {
            "message": "Script generation started",
            "level": "INFO",
            "ts": (
                datetime.datetime.utcnow().isoformat()
                + "Z"
            ),
        }

        logs.append(start_entry)

        publish_scriptgen_status(
            user_story_hierarchy_id,
            testcase_id,
            build_sse_payload(
                status="Inprogress",
                log=start_entry,
                log_index=0,
                progress=0.0,
                user_story_id=user_story_id,
                row_id=row_id,
                testcase_id=testcase_id,
                user_story_hierarchy_id=(
                    user_story_hierarchy_id
                ),
            ),
            tenant_id=tenant_id,
        )

        if job_id:
            generation_job_store.start(job_id)

        raw_generation_request = request_data_dict.get(
            "generation_request"
        )

        if not raw_generation_request:
            raise ValueError(
                "generation_request is required for "
                "agentic generation."
            )

        generation_request = (
            GenerationRequest.model_validate(
                raw_generation_request
            )
        )

        orchestrator = GenerationOrchestrator(db=db)

        async def run_agentic_generation() -> Any:
            if abort_event.is_set():
                raise asyncio.CancelledError(
                    "Task aborted before agentic generation."
                )

            log_callback(
                "Agentic generation pipeline started",
                level="INFO",
                progress=0.05,
            )

            # generate() is synchronous, so execute it outside the
            # ScriptGen asyncio event-loop thread.
            result = await asyncio.to_thread(
                orchestrator.generate,
                generation_request,
            )

            if abort_event.is_set():
                raise asyncio.CancelledError(
                    "Task aborted during agentic generation."
                )

            return result

        future = asyncio.run_coroutine_threadsafe(
            run_agentic_generation(),
            SCRIPTGEN_MAIN_LOOP,
        )

        scriptgen_status = "Failed"
        final_result: Any = None

        heartbeat_interval = 15
        last_heartbeat = time.time()

        # ----------------------------------------------------------
        # Same polling, heartbeat and abort behaviour.
        # ----------------------------------------------------------
        while True:
            try:
                generation_result = future.result(
                    timeout=0.2
                )

                final_result = (
                    ScriptGenAdapter.to_response_dict(
                        generation_result,
                        flow_steps_count=int(
                            request_data_dict.get(
                                "flow_steps_count",
                                0,
                            )
                        ),
                        automation_steps_count=int(
                            request_data_dict.get(
                                "automation_steps_count",
                                0,
                            )
                        ),
                    )
                )

                scriptgen_status = "Completed"

                log_callback(
                    "Agentic code generation completed",
                    level="INFO",
                    progress=1.0,
                )

                break

            except concurrent.futures.TimeoutError:
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

                if (
                    now - last_heartbeat
                    >= heartbeat_interval
                ):
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

            except concurrent.futures.CancelledError:
                scriptgen_status = "Aborted"
                final_result = None

                log_callback(
                    "Script generation was cancelled",
                    level="WARNING",
                )

                break

            except Exception as exc:
                scriptgen_status = "Failed"
                final_result = exc

                log_callback(
                    "Script generation encountered an error",
                    level="ERROR",
                )

                logger.exception(
                    "[AGENTIC SCRIPTGEN] Generation failed | "
                    "job_id=%s ush_id=%s testcase_id=%s",
                    job_id,
                    user_story_hierarchy_id,
                    testcase_id,
                )

                break

        # ----------------------------------------------------------
        # Same final DB status.
        # ----------------------------------------------------------
        try:
            TestCaseService.script_generation_status(
                db,
                str(user_story_hierarchy_id),
                testcase_id,
                scriptgen_status,
            )

            db.commit()

        except Exception:
            logger.exception(
                "[AGENTIC SCRIPTGEN] Final status update failed"
            )

        # ----------------------------------------------------------
        # Persist execution details using the same model.
        # ----------------------------------------------------------
        try:
            from worktop.script_generator.app.models.execution_details import (
                ExecutionDetails,
            )

            execution_details = (
                db.query(ExecutionDetails)
                .filter(
                    ExecutionDetails.user_story_hierarchy_id
                    == str(user_story_hierarchy_id),
                    ExecutionDetails.testcase_id
                    == testcase_id,
                )
                .first()
            )

            if scriptgen_status == "Aborted":
                details_dict: dict[str, Any] = {
                    "status": "Aborted",
                    "timestamp": (
                        datetime.datetime.utcnow().isoformat()
                        + "Z"
                    ),
                    "abort_details": {
                        "reason": "User requested abort"
                    },
                }

            elif isinstance(final_result, dict):
                details_dict = final_result.copy()

            else:
                details_dict = {
                    "result": (
                        str(final_result)
                        if final_result is not None
                        else None
                    )
                }

            details_dict["status"] = scriptgen_status
            details_dict["timestamp"] = (
                datetime.datetime.utcnow().isoformat()
                + "Z"
            )
            details_dict["input_data"] = {
                "generation_request": (
                    raw_generation_request
                )
            }
            details_dict["logs"] = logs.copy()
            details_dict["job_id"] = job_id

            files_changed = details_dict.get(
                "files_changed",
                [],
            )

            script_path = (
                str(files_changed[0])
                if files_changed
                else ""
            )

            if execution_details:
                execution_details.execution_details = (
                    details_dict
                )
                execution_details.script_path = script_path

            else:
                execution_details = ExecutionDetails(
                    user_story_hierarchy_id=str(
                        user_story_hierarchy_id
                    ),
                    testcase_id=testcase_id,
                    execution_details=details_dict,
                    script_path=script_path,
                )

                db.add(execution_details)

            db.commit()

        except Exception:
            logger.exception(
                "[AGENTIC SCRIPTGEN] Failed to persist "
                "execution details"
            )

        # ----------------------------------------------------------
        # Keep generation-job tracking aligned.
        # ----------------------------------------------------------
        try:
            if job_id:
                if scriptgen_status == "Completed":
                    generation_job_store.complete(
                        job_id,
                        final_result,
                    )

                elif scriptgen_status == "Aborted":
                    generation_job_store.abort(job_id)

                else:
                    generation_job_store.fail(
                        job_id,
                        final_result,
                    )

        except Exception:
            logger.exception(
                "[AGENTIC SCRIPTGEN] Job-store update failed | "
                "job_id=%s",
                job_id,
            )

        # ----------------------------------------------------------
        # Same final SSE shape.
        # ----------------------------------------------------------
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

            final_error = {
                "message": error_message,
            }

        final_payload = build_sse_payload(
            status=scriptgen_status,
            logs=logs.copy(),
            is_final=True,
            result=(
                final_result
                if scriptgen_status == "Completed"
                else None
            ),
            error=final_error,
            progress=(
                1.0
                if scriptgen_status == "Completed"
                else 0.0
                if scriptgen_status == "Aborted"
                else None
            ),
            user_story_id=user_story_id,
            row_id=row_id,
            testcase_id=testcase_id,
            user_story_hierarchy_id=(
                user_story_hierarchy_id
            ),
        )

        try:
            publish_scriptgen_status(
                user_story_hierarchy_id,
                testcase_id,
                final_payload,
                tenant_id=tenant_id,
            )

        except Exception:
            logger.exception(
                "[AGENTIC SCRIPTGEN] Failed to publish "
                "final SSE payload"
            )

        elapsed = time.time() - task_started_at

        logger.info(
            "[AGENTIC SCRIPTGEN] Task finished | "
            "job_id=%s status=%s elapsed=%.2fs",
            job_id,
            scriptgen_status,
            elapsed,
        )

    except Exception as exc:
        logger.exception(
            "[AGENTIC SCRIPTGEN] Unhandled execution failure | "
            "job_id=%s",
            job_id,
        )

        if job_id:
            with contextlib.suppress(Exception):
                generation_job_store.fail(
                    job_id,
                    exc,
                )

        with contextlib.suppress(Exception):
            publish_scriptgen_status(
                user_story_hierarchy_id,
                testcase_id,
                build_sse_payload(
                    status="Failed",
                    logs=logs.copy(),
                    is_final=True,
                    error={
                        "message": str(exc),
                    },
                    user_story_id=user_story_id,
                    row_id=row_id,
                    testcase_id=testcase_id,
                    user_story_hierarchy_id=(
                        user_story_hierarchy_id
                    ),
                ),
                tenant_id=tenant_id,
            )

    finally:
        if db_gen:
            with contextlib.suppress(Exception):
                try:
                    next(db_gen, None)
                except StopIteration:
                    pass

            if hasattr(db_gen, "close"):
                with contextlib.suppress(Exception):
                    db_gen.close()

        with _ABORT_LOCK:
            abort_signals.pop(
                abort_key,
                None,
            )