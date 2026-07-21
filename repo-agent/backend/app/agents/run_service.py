"""Owns run creation (idempotent), background execution, cancellation, and the
backend stale-run watchdog.

Dead-hang prevention (backend side): a run always reaches a terminal state. If a
background task crashes without emitting a terminal event, the done-callback
fails it; if a run stops producing activity past the stale threshold, the
watchdog fails it.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from functools import lru_cache

from app.agents.orchestrator import AgentOrchestrator
from app.config import settings
from app.logging.agent_logger import agent_logger
from app.models.agent import AgentRunError, AgentRunRequest, AgentRunView
from app.models.enums import RunStatus, StreamEventType
from app.persistence.database import get_database
from app.persistence.repositories import (
    ConversationRepository,
    MessageRepository,
    RunArtifactRepository,
    RunRepository,
)
from app.streaming.event_bus import EventBus, get_event_bus
from app.workspace.workspace_manager import WorkspaceManager


class RunService:
    def __init__(self, bus: EventBus) -> None:
        db = get_database()
        self._bus = bus
        self._runs = RunRepository(db)
        self._conversations = ConversationRepository(db)
        self._messages = MessageRepository(db)
        self._artifacts = RunArtifactRepository(db)
        self._workspaces = WorkspaceManager()
        self._orchestrator = AgentOrchestrator(
            event_bus=bus, runs=self._runs, conversations=self._conversations,
            messages=self._messages, artifacts=self._artifacts,
        )
        self._tasks: dict[str, asyncio.Task] = {}

    # --- creation (idempotent) --------------------------------------------
    async def create_run(self, request: AgentRunRequest) -> tuple[AgentRunView, bool]:
        # Idempotency: a retried POST with the same client_request_id attaches to
        # the existing run instead of creating a second one.
        if request.client_request_id:
            existing = self._runs.get_by_client_request_id(request.client_request_id)
            if existing:
                return existing, False

        # Validate the workspace up front so a bad path is a clean 400, not a run.
        workspace = self._workspaces.open_workspace(request.workspace_path)

        conversation = None
        if request.conversation_id:
            conversation = self._conversations.get(request.conversation_id)
        if conversation is None:
            conversation = self._conversations.create(str(workspace), request.mode,
                                                      title=request.message[:48] or "New Chat")

        turns = self._messages.get_turns(conversation.id)
        self._messages.add(conversation.id, "user", request.message, turn_index=len(turns))

        run = self._runs.create(conversation.id, str(workspace), request.mode, request.client_request_id)
        request = request.model_copy(update={"conversation_id": conversation.id})
        self._launch(request, run)
        return run, True

    def _launch(self, request: AgentRunRequest, run: AgentRunView) -> None:
        task = asyncio.create_task(self._orchestrator.run(request, run))
        self._tasks[run.run_id] = task
        task.add_done_callback(lambda t: self._on_task_done(run.run_id, t))

    def _on_task_done(self, run_id: str, task: asyncio.Task) -> None:
        self._tasks.pop(run_id, None)
        if task.cancelled():
            return
        exc = task.exception()
        current = self._runs.get(run_id)
        if exc is not None and current and not current.status.is_terminal:
            # Crash without a terminal event — force a terminal state.
            self._runs.set_error(run_id, AgentRunError(
                code="RUN_CRASHED", message=str(exc), recoverable=True, retry_action="start_new_run"))
            self._runs.set_status(run_id, RunStatus.FAILED)
            asyncio.create_task(self._bus.publish(run_id, StreamEventType.RUN_FAILED, {
                "error": {"code": "RUN_CRASHED", "message": str(exc)}, "status": "failed"}))

    # --- cancellation ------------------------------------------------------
    async def cancel(self, run_id: str) -> AgentRunView | None:
        run = self._runs.get(run_id)
        if not run or run.status.is_terminal:
            return run
        task = self._tasks.get(run_id)
        if task:
            task.cancel()
        self._runs.set_status(run_id, RunStatus.CANCELLED)
        await self._bus.publish(run_id, StreamEventType.RUN_CANCELLED, {"status": "cancelled"})
        agent_logger.run_cancelled({"run_id": run_id})
        return self._runs.get(run_id)

    # --- accessors ---------------------------------------------------------
    def get(self, run_id: str) -> AgentRunView | None:
        return self._runs.get(run_id)

    async def revert(self, run_id: str) -> list[str]:
        run = self._runs.get(run_id)
        if not run:
            return []
        workspace = self._workspaces.open_workspace(run.workspace_path)
        return self._orchestrator._changes.revert(run_id, workspace)

    # --- stale-run watchdog ------------------------------------------------
    async def watchdog_tick(self) -> None:
        now = datetime.now(timezone.utc)
        for run in self._runs.list_active():
            last = run.last_activity_at or run.created_at
            if last is None:
                continue
            idle = (now - last).total_seconds()
            if idle >= settings.run_stale_failure_seconds:
                self._runs.set_error(run_id=run.run_id, error=AgentRunError(
                    code="RUN_STALE", message=f"No activity for {int(idle)}s",
                    recoverable=True, retry_action="start_new_run"))
                self._runs.set_status(run.run_id, RunStatus.FAILED)
                await self._bus.publish(run.run_id, StreamEventType.RUN_FAILED, {
                    "error": {"code": "RUN_STALE"}, "status": "failed"})
                agent_logger.run_marked_stale({"run_id": run.run_id, "idle_seconds": int(idle)})

    async def run_watchdog_forever(self) -> None:
        interval = max(5, settings.heartbeat_interval_seconds)
        while True:
            await asyncio.sleep(interval)
            try:
                await self.watchdog_tick()
            except Exception:  # noqa: BLE001 - watchdog must never die
                agent_logger.event("watchdog_error")


@lru_cache
def get_run_service() -> RunService:
    return RunService(get_event_bus())
