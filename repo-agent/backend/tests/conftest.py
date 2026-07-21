"""Test fixtures: isolate each test with a fresh SQLite DB and clean singletons.

Async tests use asyncio.run() via the `run_async` helper (no pytest-asyncio).
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest

from app.config import settings
from app.persistence.database import get_database


@pytest.fixture(autouse=True)
def fresh_env(tmp_path, monkeypatch):
    """Point persistence at a throwaway DB and reset all cached singletons."""
    db_path = tmp_path / f"test_{uuid.uuid4().hex}.db"
    monkeypatch.setattr(settings, "database_path", str(db_path))

    from app.agents import run_service as run_service_mod
    from app.streaming import event_bus as event_bus_mod

    for cached in (get_database, event_bus_mod.get_event_bus, run_service_mod.get_run_service):
        cached.cache_clear()
    yield
    for cached in (get_database, event_bus_mod.get_event_bus, run_service_mod.get_run_service):
        cached.cache_clear()


@pytest.fixture
def workspace(tmp_path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "service.py").write_text("def update_status(row_id, status):\n    return row_id\n")
    (ws / "README.md").write_text("# demo\nscenario status handling\n")
    return ws


def run_async(coro):
    return asyncio.run(coro)


async def drive_to_terminal(service, request, timeout: float = 15.0):
    """Create a run and await its background task to completion."""
    run, _created = await service.create_run(request)
    task = service._tasks.get(run.run_id)
    if task is not None:
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except asyncio.TimeoutError:
            pass
    return service.get(run.run_id)
