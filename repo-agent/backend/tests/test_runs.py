"""End-to-end run lifecycle with FakeLLM: Ask, Agent, idempotency, SSE replay."""

from __future__ import annotations

from app.agents.run_service import get_run_service
from app.models.agent import AgentRunRequest
from app.models.enums import AgentMode, RunStatus
from app.persistence.database import get_database
from app.persistence.repositories import RunArtifactRepository
from app.streaming.event_bus import get_event_bus
from tests.conftest import drive_to_terminal, run_async


def test_ask_run_completes_without_changes(workspace):
    async def go():
        svc = get_run_service()
        run = await drive_to_terminal(svc, AgentRunRequest(
            workspace_path=str(workspace), mode=AgentMode.ASK, message="Explain status handling"))
        artifacts = RunArtifactRepository(get_database())
        return run, artifacts.list_file_changes(run.run_id), artifacts.list_response_batches(run.run_id)

    run, changes, batches = run_async(go())
    assert run.status == RunStatus.COMPLETED
    assert run.files_modified_count == 0
    assert len(changes) == 0
    assert len(batches) >= 2 and all(b.markdown for b in batches)


def test_agent_run_modifies_and_validates(workspace):
    async def go():
        svc = get_run_service()
        run = await drive_to_terminal(svc, AgentRunRequest(
            workspace_path=str(workspace), mode=AgentMode.AGENT,
            message="Fix scenario generation status handling"))
        artifacts = RunArtifactRepository(get_database())
        return run, artifacts.list_file_changes(run.run_id), artifacts.list_validation(run.run_id)

    run, changes, validation = run_async(go())
    assert run.status == RunStatus.COMPLETED
    assert run.files_modified_count >= 1
    assert len(changes) >= 1
    assert len(validation) == 1  # validation runs exactly once
    assert (workspace / "REPO_AGENT_NOTES.md").exists()


def test_idempotent_run_creation(workspace):
    async def go():
        svc = get_run_service()
        req = AgentRunRequest(workspace_path=str(workspace), mode=AgentMode.ASK,
                              message="hi", client_request_id="dup-key")
        run1, created1 = await svc.create_run(req)
        run2, created2 = await svc.create_run(req)
        return run1, created1, run2, created2

    run1, created1, run2, created2 = run_async(go())
    assert created1 is True and created2 is False
    assert run1.run_id == run2.run_id


def test_sse_events_are_monotonic_and_replayable(workspace):
    async def go():
        svc = get_run_service()
        run = await drive_to_terminal(svc, AgentRunRequest(
            workspace_path=str(workspace), mode=AgentMode.AGENT, message="do it"))
        bus = get_event_bus()
        all_events = bus.replay_after(run.run_id, 0)
        tail = bus.replay_after(run.run_id, all_events[len(all_events) // 2 - 1]["sequence"])
        return all_events, tail

    all_events, tail = run_async(go())
    seqs = [e["sequence"] for e in all_events]
    assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))  # strictly monotonic, unique
    assert len(tail) < len(all_events)  # replay returns only later events
    assert all_events[-1]["event_type"] == "run_completed"


def test_bad_workspace_is_rejected():
    async def go():
        svc = get_run_service()
        try:
            await svc.create_run(AgentRunRequest(
                workspace_path="/nonexistent/path/xyz", mode=AgentMode.ASK, message="x"))
            return "no-error"
        except Exception as exc:  # WorkspaceError
            return type(exc).__name__

    assert run_async(go()) == "WorkspaceError"
