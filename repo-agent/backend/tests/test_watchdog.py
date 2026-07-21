"""The stale-run watchdog guarantees a silent run still reaches a terminal state."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.agents.run_service import get_run_service
from app.config import settings
from app.models.enums import AgentMode, RunStatus
from app.persistence.database import get_database
from tests.conftest import run_async


def test_watchdog_fails_stale_run(workspace):
    async def go():
        svc = get_run_service()
        # Create a run row directly and backdate its activity beyond the failure threshold.
        run = svc._runs.create("conv_x", str(workspace), AgentMode.AGENT, None)
        svc._runs.set_status(run.run_id, RunStatus.RUNNING)
        old = (datetime.now(timezone.utc)
               - timedelta(seconds=settings.run_stale_failure_seconds + 60)).isoformat()
        get_database().execute(
            "UPDATE agent_runs SET last_activity_at=? WHERE id=?", (old, run.run_id))

        await svc.watchdog_tick()
        return svc.get(run.run_id)

    run = run_async(go())
    assert run.status == RunStatus.FAILED
    assert run.error is not None and run.error.code == "RUN_STALE"


def test_watchdog_ignores_fresh_run(workspace):
    async def go():
        svc = get_run_service()
        run = svc._runs.create("conv_y", str(workspace), AgentMode.AGENT, None)
        svc._runs.set_status(run.run_id, RunStatus.RUNNING)
        await svc.watchdog_tick()
        return svc.get(run.run_id)

    run = run_async(go())
    assert run.status == RunStatus.RUNNING  # still active, not failed
