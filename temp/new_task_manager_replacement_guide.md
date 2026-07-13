# ScriptGen task-manager replacement guide

This guide explains how to integrate `new_task_maanger.py` into the production
ScriptGen task manager. The central rule is that legacy and agentic generation
must share one lifecycle. Only the generation coroutine is selected by mode.

## Intended final flow

```text
enqueue_scriptgen_task
  -> scriptgen_worker
    -> _execute_scriptgen_task
      -> legacy generation coroutine OR _run_agentic_generation
      -> shared DB persistence
      -> shared terminal SSE
      -> shared cleanup
```

Do not keep a second agentic implementation of DB status, SSE, heartbeat,
abort handling, execution details, or cleanup.

## 1. Add the worker-type normalization helper

Copy `_normalize_worker_type` from `new_task_maanger.py` near the existing task
manager helpers.

It accepts these inputs:

- `worker_type`
- `execution_mode`
- `generation_mode`
- `is_agentic=True`

The normalized result is either `legacy` or `agentic` and is written back to
`request_data_dict["worker_type"]`.

## 2. Update `enqueue_scriptgen_task`

Keep the existing identifier extraction, DB update, replay cleanup, abort
cleanup, worker startup, queue tuple, initial SSE, and logging.

Immediately before putting the request on the queue, replace ad-hoc mode and
job-ID handling with:

```python
request_data_dict = normalize_enqueued_request(request_data_dict)
```

If the existing function adds `row_id` or other identifiers, add those values
before normalization. Do not call the agentic orchestrator from enqueue and do
not create another queue.

## 3. Replace the worker-level legacy/agentic branch

Remove this pattern from `scriptgen_worker`:

```python
if worker_type == "agentic":
    _execute_agentic_scriptgen_task(...)
else:
    _execute_scriptgen_task(...)
```

Replace it with one shared lifecycle call:

```python
_execute_scriptgen_task(
    user_story_hierarchy_id,
    testcase_id,
    request_data_dict,
)
```

Alternatively, use `execute_worker_task(..., shared_execute=_execute_scriptgen_task)`.
Keep `scriptgen_queue.task_done()` in exactly one `finally` block for every
dequeued item.

## 4. Add `_run_agentic_generation`

Copy `_run_agentic_generation` from `new_task_maanger.py` into the production
manager. It owns only the agentic engine call:

- Validate `generation_request`.
- Check the shared abort event.
- Instantiate `GenerationOrchestrator` with the existing DB session.
- Run synchronous generation through `asyncio.to_thread`.
- Convert the result using `ScriptGenAdapter.to_response_dict`.
- Return a dictionary or raise an exception.

It must not update `TestCaseService`, publish final SSE, write
`ExecutionDetails`, commit lifecycle state, clean subscribers, or remove abort
signals. Those remain in `_execute_scriptgen_task`.

## 5. Update only coroutine creation in `_execute_scriptgen_task`

Keep the current setup for the legacy service. Wrap its existing generation
call in a zero-argument factory:

```python
def legacy_coroutine_factory():
    return script_gen_service.generate_automation_script(
        testcase_steps=request_data_dict.get("testcase_steps", []),
        test_data=request_data_dict.get("test_data", {}),
        testcase_name=request_data_dict.get("testcase_name", ""),
        headless=ds_headless,
        data_config=request_data_dict.get("data_config", True),
        additional_context=request_data_dict.get("additional_context"),
        pom_required=request_data_dict.get("pom_required", True),
        user_story_id=request_data_dict.get("user_story_id"),
        abort_event=abort_event,
        log_callback=log_callback,
        transformation_metadata=request_data_dict.get(
            "transformation_metadata"
        ),
    )
```

Use the selector where the legacy coroutine was previously created:

```python
coro = select_generation_coroutine(
    user_story_hierarchy_id=user_story_hierarchy_id,
    testcase_id=testcase_id,
    request_data_dict=request_data_dict,
    db=db,
    abort_event=abort_event,
    log_callback=log_callback,
    legacy_coroutine_factory=legacy_coroutine_factory,
)

future = asyncio.run_coroutine_threadsafe(coro, SCRIPTGEN_MAIN_LOOP)
```

Everything after `future` creation remains shared: polling, heartbeat, abort,
status selection, DB persistence, execution details, final SSE, and cleanup.

## 6. Remove the duplicated agentic lifecycle

Delete the large `_execute_agentic_scriptgen_task` body that separately owns:

- A DB session
- Log buffering and SSE publication
- Heartbeats and polling
- Abort state
- Final `TestCaseService` status
- `ExecutionDetails`
- Job-store terminal state
- Final SSE
- Cleanup

Temporarily replace it with the thin compatibility wrapper from
`new_task_maanger.py` only if direct callers still exist. Pass
`shared_execute=_execute_scriptgen_task`. Delete the wrapper after all callers
use the shared entry point.

## 7. Strengthen shared failure handling

For every failed DB commit in the shared lifecycle, call `db.rollback()` before
continuing or reusing that session:

```python
except Exception:
    with contextlib.suppress(Exception):
        db.rollback()
    logger.exception("...")
```

The outermost failure handler should use a fresh DB session to persist
`Failed`, because the original session may be unusable. It must also publish a
terminal SSE payload containing:

```python
status="Failed"
is_final=True
error={"message": str(exc)}
progress=0.0
```

## 8. Persist the correct script path

Do not blindly use `files_changed[0]`. Resolve `script_path` in this order:

1. Explicit `script_path` returned by generation.
2. Explicit `generated_spec_path`.
3. First changed Playwright spec/test file.
4. Empty string if no generated spec exists.

Supporting page-object or locator files may appear before the spec in
`files_changed`.

## 9. Job-store behavior

The existing DB status and ScriptGen SSE remain authoritative for the UI. If
`generation_job_store` is retained for observability, update it only after the
shared terminal result is known. Verify its real method signatures before
calling `start`, `complete`, `abort`, or `fail`.

## 10. Verification checklist

Test all of these after integration:

1. Legacy success, failure, and abort.
2. Agentic success, validation failure, orchestrator failure, and abort.
3. Missing `job_id` and missing `generation_request`.
4. DB commit failure followed by rollback and terminal failure persistence.
5. Final SSE publication failure.
6. Subscriber reconnect/browser refresh after completion.
7. Exactly one `queue.task_done()` call per queue item.
8. Status casing remains `Inprogress`, `Completed`, `Failed`, or `Aborted`.
9. Agentic and legacy paths each publish only one terminal lifecycle result.
