"""Unit tests for the job-based generation API foundation.

FastAPI's TestClient needs httpx, which is not installed here, so the route
handlers are exercised by calling them directly with a lightweight fake Request
and monkeypatched runtime/DAO boundaries. This still covers 404/403 scoping,
serialization, accepted-response shaping and enqueue wiring.
"""

from __future__ import annotations

import asyncio
import types

import pytest
from fastapi import HTTPException

from worktop.test_agent.app.adapters.script_gen_adapter import ScriptGenAdapter
from worktop.test_agent.app.api.routes import (
    event_routes,
    generation_routes,
    job_routes,
)
from worktop.test_agent.app.runtime import scriptgen_runtime
from worktop.test_agent.app.schemas.generation_status import (
    JOB_ABORTED,
    JOB_COMPLETED,
    JOB_RUNNING,
    SSE_ABORTING,
    SSE_COMPLETED,
    SSE_IN_PROGRESS,
    to_sse_status,
)
from worktop.test_agent.app.schemas.playwright_generation_api import (
    PlaywrightGenerationRequest,
)
from worktop.test_agent.app.services.generation_job_store import GenerationJobStore


def _request(tenant_id=7, headers=None):
    return types.SimpleNamespace(
        state=types.SimpleNamespace(tenant_id=tenant_id),
        headers=headers or {},
    )


@pytest.fixture
def store(monkeypatch):
    """Fresh job store wired into all three route modules."""
    fresh = GenerationJobStore()
    monkeypatch.setattr(generation_routes, "generation_job_store", fresh)
    monkeypatch.setattr(job_routes, "generation_job_store", fresh)
    monkeypatch.setattr(event_routes, "generation_job_store", fresh)
    return fresh


# --------------------------------------------------------------------------- #
# Status mapping
# --------------------------------------------------------------------------- #
class TestStatusMapping:
    def test_running_and_queued_are_in_progress(self):
        assert to_sse_status("queued") == SSE_IN_PROGRESS
        assert to_sse_status(JOB_RUNNING) == SSE_IN_PROGRESS

    def test_terminal_and_aborting(self):
        assert to_sse_status(JOB_COMPLETED) == SSE_COMPLETED
        assert to_sse_status("abort_requested") == SSE_ABORTING

    def test_unknown_defaults_to_in_progress(self):
        assert to_sse_status("something_new") == SSE_IN_PROGRESS


# --------------------------------------------------------------------------- #
# Job store
# --------------------------------------------------------------------------- #
class TestJobStore:
    def _create(self, store):
        return store.create(
            job_id="j1",
            user_story_hierarchy_id=100,
            testcase_id="TC-1",
            tenant_id=7,
            automation_steps_count=3,
            flow_steps_count=2,
        )

    def test_create_and_get_snapshot(self):
        store = GenerationJobStore()
        self._create(store)
        job = store.get("j1")
        assert job["status"] == "queued"
        assert job["tenant_id"] == 7
        # get returns a copy, not the live record
        job["status"] = "mutated"
        assert store.get("j1")["status"] == "queued"

    def test_get_unknown_returns_none(self):
        assert GenerationJobStore().get("nope") is None

    def test_duplicate_create_raises(self):
        store = GenerationJobStore()
        self._create(store)
        with pytest.raises(ValueError):
            self._create(store)

    def test_lifecycle_running_progress_complete(self):
        store = GenerationJobStore()
        self._create(store)
        store.mark_running("j1")
        assert store.get("j1")["status"] == JOB_RUNNING
        assert store.get("j1")["started_at"] is not None
        store.mark_progress("j1", 2.0)  # clamped
        assert store.get("j1")["progress"] == 1.0
        store.complete("j1", {"files_changed": ["a.ts"]})
        job = store.get("j1")
        assert job["status"] == JOB_COMPLETED
        assert job["result"] == {"files_changed": ["a.ts"]}
        assert job["completed_at"] is not None

    def test_terminal_guard_blocks_resurrection(self):
        store = GenerationJobStore()
        self._create(store)
        store.complete("j1", {"ok": True})
        store.mark_running("j1")  # must be ignored
        assert store.get("j1")["status"] == JOB_COMPLETED

    def test_abort_is_terminal_and_idempotent(self):
        store = GenerationJobStore()
        self._create(store)
        store.abort("j1", error="cancelled")
        assert store.get("j1")["status"] == JOB_ABORTED
        store.abort("j1", error="again")
        assert store.get("j1")["error"] == "cancelled"

    def test_fail_records_error(self):
        store = GenerationJobStore()
        self._create(store)
        store.fail("j1", "boom")
        job = store.get("j1")
        assert job["status"] == "failed"
        assert job["error"] == "boom"


# --------------------------------------------------------------------------- #
# ScriptGenAdapter
# --------------------------------------------------------------------------- #
class TestScriptGenAdapter:
    def test_prepend_puts_flow_steps_first(self):
        combined, count = ScriptGenAdapter.prepend_flow_steps(
            ["Login", "Navigate"], ["Open payroll", "Validate"]
        )
        assert combined == ["Login", "Navigate", "Open payroll", "Validate"]
        assert count == 2

    def test_prepend_filters_blank_flow_steps(self):
        combined, count = ScriptGenAdapter.prepend_flow_steps(
            ["Login", "  ", "", None], ["Step"]  # type: ignore[list-item]
        )
        assert combined == ["Login", "Step"]
        assert count == 1

    def test_to_generation_request_maps_fields(self):
        req = ScriptGenAdapter.to_generation_request(
            job_id="j1",
            repo_path="/repo",
            tenant_id=7,
            testcase_id="TC-1",
            automation_steps=["a", "b"],
            testcase_name="Login flow",
        )
        assert req.job_id == "j1"
        assert req.repo_path == "/repo"
        assert req.tenant_id == "7"  # coerced to str
        assert req.test_case_name == "Login flow"
        assert req.steps == ["a", "b"]

    def test_to_generation_request_falls_back_to_testcase_id_for_name(self):
        req = ScriptGenAdapter.to_generation_request(
            job_id="j1",
            repo_path="/repo",
            tenant_id=None,
            testcase_id="TC-9",
            automation_steps=[],
            testcase_name="",
        )
        assert req.test_case_name == "TC-9"
        assert req.tenant_id is None

    def test_normalize_flow_steps_variants(self):
        assert ScriptGenAdapter._normalize_flow_steps(None) == []
        assert ScriptGenAdapter._normalize_flow_steps('["a", "b"]') == ["a", "b"]
        assert ScriptGenAdapter._normalize_flow_steps(["a", " ", "b"]) == ["a", "b"]
        assert ScriptGenAdapter._normalize_flow_steps({"steps": ["x"]}) == ["x"]
        assert ScriptGenAdapter._normalize_flow_steps("just text") == ["just text"]

    def test_extract_flow_steps_returns_empty_without_platform_dao(self):
        # core_services DAO is not importable here → best-effort empty list
        assert ScriptGenAdapter.extract_flow_steps(db=None, user_story_hierarchy_id=1) == []


# --------------------------------------------------------------------------- #
# job_routes
# --------------------------------------------------------------------------- #
class TestJobRoutes:
    def _seed(self, store):
        store.create(
            job_id="j1",
            user_story_hierarchy_id=100,
            testcase_id="TC-1",
            tenant_id=7,
            automation_steps_count=3,
            flow_steps_count=2,
        )

    def test_get_unknown_job_404(self, store):
        with pytest.raises(HTTPException) as exc:
            job_routes.get_generation_job("missing", _request())
        assert exc.value.status_code == 404

    def test_get_cross_tenant_403(self, store):
        self._seed(store)
        with pytest.raises(HTTPException) as exc:
            job_routes.get_generation_job("j1", _request(tenant_id=999))
        assert exc.value.status_code == 403

    def test_get_returns_serialized_result(self, store):
        self._seed(store)

        class _Result:
            def model_dump(self, mode="json"):
                return {"files_changed": ["x.ts"], "mode": mode}

        store.complete("j1", _Result())
        job = job_routes.get_generation_job("j1", _request())
        assert job.status == "completed"
        assert job.result == {"files_changed": ["x.ts"], "mode": "json"}
        assert job.automation_steps_count == 3
        assert job.flow_steps_count == 2

    def test_abort_unknown_404(self, store):
        with pytest.raises(HTTPException) as exc:
            job_routes.abort_generation_job("missing", _request())
        assert exc.value.status_code == 404

    def test_abort_terminal_returns_message(self, store):
        self._seed(store)
        store.complete("j1", {"ok": True})
        resp = job_routes.abort_generation_job("j1", _request())
        assert resp.status == "completed"
        assert "terminal" in resp.message

    def test_abort_active_calls_runtime_and_marks_requested(self, store, monkeypatch):
        self._seed(store)
        calls = {}

        def fake_abort(**kwargs):
            calls.update(kwargs)
            return {"status": "abort_requested", "message": "signal sent"}

        monkeypatch.setattr(scriptgen_runtime, "abort_task", fake_abort)
        resp = job_routes.abort_generation_job("j1", _request())
        assert resp.status == "abort_requested"
        assert resp.message == "signal sent"
        assert calls["user_story_hierarchy_id"] == 100
        assert calls["tenant_id"] == 7
        assert store.get("j1")["abort_requested"] is True

    def test_abort_runtime_unavailable_503(self, store, monkeypatch):
        self._seed(store)

        def boom(**kwargs):
            raise scriptgen_runtime.RuntimeUnavailableError("nope")

        monkeypatch.setattr(scriptgen_runtime, "abort_task", boom)
        with pytest.raises(HTTPException) as exc:
            job_routes.abort_generation_job("j1", _request())
        assert exc.value.status_code == 503


# --------------------------------------------------------------------------- #
# generation_routes
# --------------------------------------------------------------------------- #
class TestGenerationRoute:
    def _payload(self, **over):
        base = dict(
            user_story_hierarchy_id=100,
            testcase_id="TC-1",
            testcase_steps=["Click"],
        )
        base.update(over)
        return PlaywrightGenerationRequest(**base)

    def test_happy_path_returns_202_shape_and_enqueues(self, store, monkeypatch):
        enqueued = {}
        monkeypatch.setattr(
            generation_routes, "_resolve_repository_path", lambda db: "/repo"
        )
        monkeypatch.setattr(
            ScriptGenAdapter, "extract_flow_steps", staticmethod(lambda db, h: ["Login", "Nav"])
        )
        monkeypatch.setattr(
            scriptgen_runtime,
            "enqueue_agent_generation_task",
            lambda **kw: enqueued.update(kw),
        )

        resp = asyncio.run(
            generation_routes.generate_playwright_test(
                _request(tenant_id=7), self._payload(), db=None
            )
        )
        assert resp.status == "queued"
        assert resp.testcase_id == "TC-1"
        assert resp.automation_steps_count == 1  # only testcase steps counted
        assert resp.flow_steps_count == 2

        # job stored and enqueue wired with combined steps (flow first)
        assert store.get(resp.job_id)["status"] == "queued"
        assert enqueued["tenant_id"] == 7
        assert enqueued["generation_request"]["steps"] == ["Login", "Nav", "Click"]

    def test_tenant_mismatch_403(self, store, monkeypatch):
        monkeypatch.setattr(
            generation_routes, "_resolve_repository_path", lambda db: "/repo"
        )
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                generation_routes.generate_playwright_test(
                    _request(tenant_id=7),
                    self._payload(tenant_id=999),
                    db=None,
                )
            )
        assert exc.value.status_code == 403

    def test_runtime_unavailable_marks_failed_and_503(self, store, monkeypatch):
        monkeypatch.setattr(
            generation_routes, "_resolve_repository_path", lambda db: "/repo"
        )

        def boom(**kw):
            raise scriptgen_runtime.RuntimeUnavailableError("no runtime")

        monkeypatch.setattr(
            scriptgen_runtime, "enqueue_agent_generation_task", boom
        )
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                generation_routes.generate_playwright_test(
                    _request(tenant_id=7), self._payload(), db=None
                )
            )
        assert exc.value.status_code == 503
        # the created job is marked failed so a later GET reflects it
        jobs = [j for j in store._jobs.values()]  # noqa: SLF001 - test introspection
        assert jobs and jobs[0]["status"] == "failed"

    def test_missing_authenticated_tenant_401(self, store):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                generation_routes.generate_playwright_test(
                    _request(tenant_id=None), self._payload(), db=None
                )
            )
        assert exc.value.status_code == 401


# --------------------------------------------------------------------------- #
# event_routes
# --------------------------------------------------------------------------- #
class TestEventRoute:
    def _seed(self, store):
        store.create(
            job_id="j1",
            user_story_hierarchy_id=100,
            testcase_id="TC-1",
            tenant_id=7,
        )

    def test_unknown_job_404(self, store):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(event_routes.stream_generation_events("missing", _request()))
        assert exc.value.status_code == 404

    def test_cross_tenant_403(self, store):
        self._seed(store)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                event_routes.stream_generation_events("j1", _request(tenant_id=2))
            )
        assert exc.value.status_code == 403

    def test_happy_path_subscribes_and_streams(self, store, monkeypatch):
        subscribed = {}

        async def fake_generator(**kwargs):
            yield ": ping\n\n"

        monkeypatch.setattr(
            scriptgen_runtime, "make_key", lambda h, t, ten: (h, t, ten)
        )
        monkeypatch.setattr(
            scriptgen_runtime,
            "subscribe_scriptgen_status",
            lambda key, queue: subscribed.update(key=key),
        )
        monkeypatch.setattr(
            scriptgen_runtime, "generation_status_event_generator", fake_generator
        )

        self._seed(store)
        resp = asyncio.run(
            event_routes.stream_generation_events("j1", _request(tenant_id=7))
        )
        assert resp.media_type == "text/event-stream"
        assert resp.headers["X-Accel-Buffering"] == "no"
        assert subscribed["key"] == (100, "TC-1", 7)

    def test_runtime_unavailable_503(self, store, monkeypatch):
        self._seed(store)

        def boom(*a, **k):
            raise scriptgen_runtime.RuntimeUnavailableError("no runtime")

        monkeypatch.setattr(scriptgen_runtime, "make_key", boom)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                event_routes.stream_generation_events("j1", _request(tenant_id=7))
            )
        assert exc.value.status_code == 503
