import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.ai_workspace.domain.chat_message import ChatMessage, ChatRole
from app.ai_workspace.domain.execution_context import (
    ExecutionContext,
    ExecutionStage,
    ExecutionStageStatus,
    ExecutionStatus,
)
from app.ai_workspace.domain.execution_plan import ExecutionPlan, ExecutionPlanStep, PlannedToolCall
from app.ai_workspace.domain.file_change import DiffHunk, DiffLine, FileChange, FileChangeStatus
from app.ai_workspace.domain.review_decision import ReviewDecision
from app.ai_workspace.domain.workspace_mode import WorkspaceMode
from app.ai_workspace.domain.workspace_runtime import WorkspaceRuntime
from app.ai_workspace.domain.workspace_session import WorkspaceSession
from app.ai_workspace.infrastructure.state_store import StateStore


class SQLiteStateStore:
    """Small durable key-value store for AI Workspace state.

    This is intentionally conservative: it preserves the existing store interfaces while
    making state survive process restarts. A host application can later replace this with
    first-class relational tables without touching the service layer.
    """

    def __init__(self, db_path: str):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def set(self, namespace: str, key: str, payload: dict | list) -> None:
        encoded = json.dumps(payload)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ai_workspace_state(namespace, key, payload, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(namespace, key)
                DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
                """,
                (namespace, key, encoded, now),
            )

    def get(self, namespace: str, key: str) -> dict | list | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM ai_workspace_state WHERE namespace = ? AND key = ?",
                (namespace, key),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, namespace: str) -> list[tuple[str, dict | list]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT key, payload FROM ai_workspace_state WHERE namespace = ?",
                (namespace,),
            ).fetchall()
        return [(key, json.loads(payload)) for key, payload in rows]

    def delete(self, namespace: str, key: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "DELETE FROM ai_workspace_state WHERE namespace = ? AND key = ?",
                (namespace, key),
            )

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_workspace_state (
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(namespace, key)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)


class SQLiteSessionStore:
    def __init__(self, state: StateStore):
        self._state = state

    def save_session(self, session: WorkspaceSession) -> None:
        self._state.set("sessions", session.id, _session_to_dict(session))
        if self._state.get("messages", session.id) is None:
            self._state.set("messages", session.id, [])

    def get_session(self, session_id: str) -> WorkspaceSession | None:
        payload = self._state.get("sessions", session_id)
        return _session_from_dict(payload) if isinstance(payload, dict) else None

    def list_sessions(self, repository_path: str | None = None) -> list[WorkspaceSession]:
        sessions = [
            _session_from_dict(payload)
            for _, payload in self._state.list("sessions")
            if isinstance(payload, dict)
        ]
        if repository_path:
            sessions = [session for session in sessions if session.repository_path == repository_path]
        return sorted(sessions, key=lambda session: session.last_activity_at, reverse=True)

    def append_message(self, message: ChatMessage) -> None:
        messages = self._state.get("messages", message.session_id)
        items = messages if isinstance(messages, list) else []
        items.append(_message_to_dict(message))
        self._state.set("messages", message.session_id, items)

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        messages = self._state.get("messages", session_id)
        if not isinstance(messages, list):
            return []
        return [_message_from_dict(item) for item in messages if isinstance(item, dict)]

    def delete_session(self, session_id: str) -> None:
        self._state.delete("sessions", session_id)
        self._state.delete("messages", session_id)


class SQLiteRuntimeStore:
    def __init__(self, state: StateStore):
        self._state = state

    def get(self, session_id: str) -> WorkspaceRuntime | None:
        payload = self._state.get("runtimes", session_id)
        return _runtime_from_dict(payload) if isinstance(payload, dict) else None

    def set(self, runtime: WorkspaceRuntime) -> None:
        self._state.set("runtimes", runtime.session_id, _runtime_to_dict(runtime))

    def delete(self, session_id: str) -> None:
        self._state.delete("runtimes", session_id)


class SQLiteExecutionStore:
    def __init__(self, state: StateStore):
        self._state = state

    def save(self, execution: ExecutionContext) -> None:
        self._state.set("executions", execution.execution_id, _execution_to_dict(execution))

    def get(self, execution_id: str) -> ExecutionContext | None:
        payload = self._state.get("executions", execution_id)
        return _execution_from_dict(payload) if isinstance(payload, dict) else None


class SQLitePlanStore:
    def __init__(self, state: StateStore):
        self._state = state

    def save(self, plan: ExecutionPlan) -> None:
        self._state.set("plans", plan.execution_id, _plan_to_dict(plan))

    def get(self, execution_id: str) -> ExecutionPlan | None:
        payload = self._state.get("plans", execution_id)
        return _plan_from_dict(payload) if isinstance(payload, dict) else None

    def delete(self, execution_id: str) -> None:
        self._state.delete("plans", execution_id)


class SQLiteReviewStore:
    def __init__(self, state: StateStore):
        self._state = state

    def save_changes(self, run_id: str, changes: list[FileChange]) -> None:
        self._state.set("reviews", run_id, [_file_change_to_dict(change) for change in changes])

    def get_changes(self, run_id: str) -> list[FileChange]:
        payload = self._state.get("reviews", run_id)
        if not isinstance(payload, list):
            return []
        return [_file_change_from_dict(item) for item in payload if isinstance(item, dict)]

    def update_decision(self, run_id: str, file_id: str, decision) -> None:
        changes = self.get_changes(run_id)
        for change in changes:
            if change.id == file_id:
                change.decision = ReviewDecision(decision)
        self.save_changes(run_id, changes)

    def clear(self, run_id: str) -> None:
        self._state.delete("reviews", run_id)


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _session_to_dict(session: WorkspaceSession) -> dict:
    return {
        "id": session.id,
        "tenant_id": session.tenant_id,
        "repository_path": session.repository_path,
        "branch": session.branch,
        "mode": session.mode.value,
        "current_task": session.current_task,
        "started_at": _dt(session.started_at),
        "last_activity_at": _dt(session.last_activity_at),
    }


def _session_from_dict(payload: dict) -> WorkspaceSession:
    return WorkspaceSession(
        id=payload["id"],
        tenant_id=payload["tenant_id"],
        repository_path=payload["repository_path"],
        branch=payload["branch"],
        mode=WorkspaceMode(payload["mode"]),
        current_task=payload.get("current_task"),
        started_at=_parse_dt(payload["started_at"]),
        last_activity_at=_parse_dt(payload["last_activity_at"]),
    )


def _message_to_dict(message: ChatMessage) -> dict:
    return {
        "id": message.id,
        "session_id": message.session_id,
        "role": message.role.value,
        "content": message.content,
        "created_at": _dt(message.created_at),
        "execution_id": message.execution_id,
    }


def _message_from_dict(payload: dict) -> ChatMessage:
    return ChatMessage(
        id=payload["id"],
        session_id=payload["session_id"],
        role=ChatRole(payload["role"]),
        content=payload["content"],
        created_at=_parse_dt(payload["created_at"]),
        execution_id=payload.get("execution_id"),
    )


def _runtime_to_dict(runtime: WorkspaceRuntime) -> dict:
    return {
        "workspace_path": runtime.workspace_path,
        "session_id": runtime.session_id,
        "selected_model_id": runtime.selected_model_id,
        "selected_file_paths": runtime.selected_file_paths,
        "enabled_tool_ids": runtime.enabled_tool_ids,
        "mode": runtime.mode.value,
    }


def _runtime_from_dict(payload: dict) -> WorkspaceRuntime:
    return WorkspaceRuntime(
        workspace_path=payload["workspace_path"],
        session_id=payload["session_id"],
        selected_model_id=payload.get("selected_model_id"),
        selected_file_paths=list(payload.get("selected_file_paths", [])),
        enabled_tool_ids=list(payload.get("enabled_tool_ids", [])),
        mode=WorkspaceMode(payload.get("mode", WorkspaceMode.AGENT.value)),
    )


def _execution_to_dict(execution: ExecutionContext) -> dict:
    return {
        "execution_id": execution.execution_id,
        "session_id": execution.session_id,
        "tenant_id": execution.tenant_id,
        "mode": execution.mode.value,
        "prompt": execution.prompt,
        "correlation_id": execution.correlation_id,
        "started_at": _dt(execution.started_at),
        "status": execution.status.value,
        "stages": [
            {
                "id": stage.id,
                "label": stage.label,
                "status": stage.status.value,
                "detail": stage.detail,
            }
            for stage in execution.stages
        ],
        "completed_at": _dt(execution.completed_at),
        "error_message": execution.error_message,
    }


def _execution_from_dict(payload: dict) -> ExecutionContext:
    return ExecutionContext(
        execution_id=payload["execution_id"],
        session_id=payload["session_id"],
        tenant_id=payload["tenant_id"],
        mode=WorkspaceMode(payload["mode"]),
        prompt=payload["prompt"],
        correlation_id=payload["correlation_id"],
        started_at=_parse_dt(payload["started_at"]),
        status=ExecutionStatus(payload["status"]),
        stages=[
            ExecutionStage(
                id=stage["id"],
                label=stage["label"],
                status=ExecutionStageStatus(stage["status"]),
                detail=stage.get("detail"),
            )
            for stage in payload.get("stages", [])
        ],
        completed_at=_parse_dt(payload.get("completed_at")),
        error_message=payload.get("error_message"),
    )


def _plan_to_dict(plan: ExecutionPlan) -> dict:
    return {
        "execution_id": plan.execution_id,
        "steps": [
            {
                "order": step.order,
                "description": step.description,
                "affected_files": step.affected_files,
                "tool_calls": [
                    {"tool_name": tool_call.tool_name, "arguments": tool_call.arguments}
                    for tool_call in step.tool_calls
                ],
                "confidence": step.confidence,
            }
            for step in plan.steps
        ],
        "overall_confidence": plan.overall_confidence,
    }


def _plan_from_dict(payload: dict) -> ExecutionPlan:
    return ExecutionPlan(
        execution_id=payload["execution_id"],
        steps=[
            ExecutionPlanStep(
                order=step["order"],
                description=step["description"],
                affected_files=list(step.get("affected_files", [])),
                tool_calls=[
                    PlannedToolCall(tool_name=tool_call["tool_name"], arguments=tool_call.get("arguments", {}))
                    for tool_call in step.get("tool_calls", [])
                ],
                confidence=step.get("confidence"),
            )
            for step in payload.get("steps", [])
        ],
        overall_confidence=payload.get("overall_confidence"),
    )


def _file_change_to_dict(change: FileChange) -> dict:
    return {
        "id": change.id,
        "run_id": change.run_id,
        "file_path": change.file_path,
        "status": change.status.value,
        "additions": change.additions,
        "deletions": change.deletions,
        "new_content": change.new_content,
        "diff_hunks": [
            {
                "header": hunk.header,
                "lines": [
                    {
                        "type": line.type,
                        "old_line_number": line.old_line_number,
                        "new_line_number": line.new_line_number,
                        "content": line.content,
                    }
                    for line in hunk.lines
                ],
            }
            for hunk in change.diff_hunks
        ],
        "decision": change.decision.value,
    }


def _file_change_from_dict(payload: dict) -> FileChange:
    return FileChange(
        id=payload["id"],
        run_id=payload["run_id"],
        file_path=payload["file_path"],
        status=FileChangeStatus(payload["status"]),
        additions=payload["additions"],
        deletions=payload["deletions"],
        new_content=payload["new_content"],
        diff_hunks=[
            DiffHunk(
                header=hunk["header"],
                lines=[
                    DiffLine(
                        type=line["type"],
                        old_line_number=line.get("old_line_number"),
                        new_line_number=line.get("new_line_number"),
                        content=line["content"],
                    )
                    for line in hunk.get("lines", [])
                ],
            )
            for hunk in payload.get("diff_hunks", [])
        ],
        decision=ReviewDecision(payload.get("decision", ReviewDecision.PENDING.value)),
    )
