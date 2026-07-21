"""Repository classes mapping domain models <-> SQLite rows.

Consolidated into one module (they share a Database); richer nested objects are
stored as JSON payloads to avoid a wide relational schema.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.models.agent import AgentRunError, AgentRunView
from app.models.changes import FileChange, ValidationResult
from app.models.conversation import Conversation, ConversationSummary, Message
from app.models.enums import AgentMode, RunStatus
from app.models.plan import ExecutionPlan
from app.models.response import ResponseBatch
from app.persistence.database import Database


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Conversations & messages
# --------------------------------------------------------------------------- #
class ConversationRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, workspace_path: str, mode: AgentMode, title: str = "New Chat") -> Conversation:
        conv = Conversation(id=_new_id("conv"), workspace_path=workspace_path, mode=mode, title=title)
        self._db.execute(
            "INSERT INTO conversations (id, workspace_path, title, mode, turn_count, "
            "compaction_count, active_summary_id, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                conv.id, conv.workspace_path, conv.title, conv.mode.value, conv.turn_count,
                conv.compaction_count, conv.active_summary_id,
                conv.created_at.isoformat(), conv.updated_at.isoformat(),
            ),
        )
        return conv

    def get(self, conversation_id: str) -> Conversation | None:
        row = self._db.query_one("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
        return self._row_to_conv(row) if row else None

    def list(self, limit: int = 20) -> list[Conversation]:
        rows = self._db.query_all(
            "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,)
        )
        return [self._row_to_conv(r) for r in rows]

    def delete(self, conversation_id: str) -> None:
        self._db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        self._db.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))

    def touch(self, conversation_id: str, *, title: str | None = None,
              turn_count: int | None = None, compaction_count: int | None = None,
              active_summary_id: str | None = None) -> None:
        conv = self.get(conversation_id)
        if not conv:
            return
        title = title if title is not None else conv.title
        turn_count = turn_count if turn_count is not None else conv.turn_count
        compaction_count = compaction_count if compaction_count is not None else conv.compaction_count
        active_summary_id = active_summary_id if active_summary_id is not None else conv.active_summary_id
        self._db.execute(
            "UPDATE conversations SET title=?, turn_count=?, compaction_count=?, "
            "active_summary_id=?, updated_at=? WHERE id=?",
            (title, turn_count, compaction_count, active_summary_id, _now_iso(), conversation_id),
        )

    def save_summary(self, conversation_id: str, summary: ConversationSummary) -> str:
        summary_id = _new_id("sum")
        self._db.execute(
            "INSERT INTO conversation_summaries (id, conversation_id, payload, created_at) VALUES (?,?,?,?)",
            (summary_id, conversation_id, summary.model_dump_json(), _now_iso()),
        )
        self.touch(conversation_id, active_summary_id=summary_id)
        return summary_id

    def get_active_summary(self, conversation_id: str) -> ConversationSummary | None:
        conv = self.get(conversation_id)
        if not conv or not conv.active_summary_id:
            return None
        row = self._db.query_one(
            "SELECT payload FROM conversation_summaries WHERE id = ?", (conv.active_summary_id,)
        )
        return ConversationSummary.model_validate_json(row["payload"]) if row else None

    @staticmethod
    def _row_to_conv(row) -> Conversation:
        return Conversation(
            id=row["id"], workspace_path=row["workspace_path"], title=row["title"],
            mode=AgentMode(row["mode"]), turn_count=row["turn_count"],
            compaction_count=row["compaction_count"], active_summary_id=row["active_summary_id"],
            created_at=_parse_dt(row["created_at"]), updated_at=_parse_dt(row["updated_at"]),
        )


class MessageRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, conversation_id: str, role: str, content: str,
            run_id: str | None = None, turn_index: int = 0) -> Message:
        msg = Message(id=_new_id("msg"), conversation_id=conversation_id, role=role,
                      content=content, run_id=run_id, turn_index=turn_index)
        self._db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, run_id, turn_index, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (msg.id, conversation_id, role, content, run_id, turn_index, msg.created_at.isoformat()),
        )
        return msg

    def list_for_conversation(self, conversation_id: str) -> list[Message]:
        rows = self._db.query_all(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
        return [
            Message(id=r["id"], conversation_id=r["conversation_id"], role=r["role"],
                    content=r["content"], run_id=r["run_id"], turn_index=r["turn_index"],
                    created_at=_parse_dt(r["created_at"]))
            for r in rows
        ]

    def get_turns(self, conversation_id: str) -> list[dict]:
        """Group messages into (user, assistant) turns for compaction."""
        messages = self.list_for_conversation(conversation_id)
        turns: list[dict] = []
        current: dict = {}
        for m in messages:
            if m.role == "user":
                if current:
                    turns.append(current)
                current = {"user": m.content, "assistant": None}
            elif m.role == "assistant" and current:
                current["assistant"] = m.content
        if current:
            turns.append(current)
        return turns


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #
class RunRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, conversation_id: str, workspace_path: str, mode: AgentMode,
               client_request_id: str | None) -> AgentRunView:
        run_id = _new_id("run")
        now = _now_iso()
        self._db.execute(
            "INSERT INTO agent_runs (id, conversation_id, workspace_path, mode, status, "
            "agent_state, client_request_id, created_at, updated_at, last_activity_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (run_id, conversation_id, workspace_path, mode.value, RunStatus.QUEUED.value,
             None, client_request_id, now, now, now),
        )
        return self.get(run_id)

    def get(self, run_id: str) -> AgentRunView | None:
        row = self._db.query_one("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
        return self._row_to_view(row) if row else None

    def get_by_client_request_id(self, client_request_id: str) -> AgentRunView | None:
        row = self._db.query_one(
            "SELECT * FROM agent_runs WHERE client_request_id = ?", (client_request_id,)
        )
        return self._row_to_view(row) if row else None

    def list_active(self) -> list[AgentRunView]:
        rows = self._db.query_all(
            "SELECT * FROM agent_runs WHERE status IN (?,?,?,?,?)",
            (RunStatus.QUEUED.value, RunStatus.PLANNING.value, RunStatus.RUNNING.value,
             RunStatus.WAITING_FOR_AUTH.value, RunStatus.VALIDATING.value),
        )
        return [self._row_to_view(r) for r in rows]

    def set_status(self, run_id: str, status: RunStatus, agent_state: str | None = None) -> None:
        now = _now_iso()
        if agent_state is not None:
            self._db.execute(
                "UPDATE agent_runs SET status=?, agent_state=?, updated_at=?, last_activity_at=? WHERE id=?",
                (status.value, agent_state, now, now, run_id),
            )
        else:
            self._db.execute(
                "UPDATE agent_runs SET status=?, updated_at=?, last_activity_at=? WHERE id=?",
                (status.value, now, now, run_id),
            )

    def set_error(self, run_id: str, error: AgentRunError) -> None:
        self._db.execute(
            "UPDATE agent_runs SET error=?, updated_at=? WHERE id=?",
            (error.model_dump_json(), _now_iso(), run_id),
        )

    def touch_activity(self, run_id: str, sequence: int | None = None) -> None:
        if sequence is not None:
            self._db.execute(
                "UPDATE agent_runs SET last_event_sequence=?, last_activity_at=? WHERE id=?",
                (sequence, _now_iso(), run_id),
            )
        else:
            self._db.execute(
                "UPDATE agent_runs SET last_activity_at=? WHERE id=?", (_now_iso(), run_id)
            )

    def update_counters(self, run_id: str, *, plan_revision: int | None = None,
                        tool_call_count: int | None = None, files_read_count: int | None = None,
                        files_modified_count: int | None = None) -> None:
        view = self.get(run_id)
        if not view:
            return
        self._db.execute(
            "UPDATE agent_runs SET plan_revision=?, tool_call_count=?, files_read_count=?, "
            "files_modified_count=?, updated_at=? WHERE id=?",
            (
                plan_revision if plan_revision is not None else view.plan_revision,
                tool_call_count if tool_call_count is not None else view.tool_call_count,
                files_read_count if files_read_count is not None else view.files_read_count,
                files_modified_count if files_modified_count is not None else view.files_modified_count,
                _now_iso(), run_id,
            ),
        )

    @staticmethod
    def _row_to_view(row) -> AgentRunView:
        error = None
        if row["error"]:
            error = AgentRunError.model_validate_json(row["error"])
        return AgentRunView(
            run_id=row["id"], conversation_id=row["conversation_id"],
            workspace_path=row["workspace_path"], mode=AgentMode(row["mode"]),
            status=RunStatus(row["status"]), agent_state=row["agent_state"],
            last_event_sequence=row["last_event_sequence"], plan_revision=row["plan_revision"],
            tool_call_count=row["tool_call_count"], files_read_count=row["files_read_count"],
            files_modified_count=row["files_modified_count"], error=error,
            created_at=_parse_dt(row["created_at"]), updated_at=_parse_dt(row["updated_at"]),
            last_activity_at=_parse_dt(row["last_activity_at"]),
        )


# --------------------------------------------------------------------------- #
# Events (SSE replay) + run artifacts
# --------------------------------------------------------------------------- #
class EventRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def append(self, run_id: str, sequence: int, event_type: str,
               payload: dict, created_at: str) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO run_events (run_id, sequence, event_type, payload, created_at) "
            "VALUES (?,?,?,?,?)",
            (run_id, sequence, event_type, json.dumps(payload, default=str), created_at),
        )

    def list_after(self, run_id: str, after_sequence: int) -> list[dict]:
        rows = self._db.query_all(
            "SELECT sequence, event_type, payload, created_at FROM run_events "
            "WHERE run_id = ? AND sequence > ? ORDER BY sequence ASC",
            (run_id, after_sequence),
        )
        return [
            {"sequence": r["sequence"], "event_type": r["event_type"],
             "payload": json.loads(r["payload"]), "created_at": r["created_at"]}
            for r in rows
        ]


class RunArtifactRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    # plan
    def save_plan(self, run_id: str, plan: ExecutionPlan) -> None:
        self._db.execute(
            "INSERT INTO run_plans (run_id, payload, revision, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(run_id) DO UPDATE SET payload=excluded.payload, "
            "revision=excluded.revision, updated_at=excluded.updated_at",
            (run_id, plan.model_dump_json(), plan.revision, _now_iso()),
        )

    def get_plan(self, run_id: str) -> ExecutionPlan | None:
        row = self._db.query_one("SELECT payload FROM run_plans WHERE run_id = ?", (run_id,))
        return ExecutionPlan.model_validate_json(row["payload"]) if row else None

    # response batches
    def save_response_batch(self, batch: ResponseBatch) -> None:
        self._db.execute(
            "INSERT INTO response_batches (run_id, batch_index, payload) VALUES (?,?,?) "
            "ON CONFLICT(run_id, batch_index) DO UPDATE SET payload=excluded.payload",
            (batch.run_id, batch.index, batch.model_dump_json()),
        )

    def list_response_batches(self, run_id: str) -> list[ResponseBatch]:
        rows = self._db.query_all(
            "SELECT payload FROM response_batches WHERE run_id = ? ORDER BY batch_index ASC", (run_id,)
        )
        return [ResponseBatch.model_validate_json(r["payload"]) for r in rows]

    # file changes
    def add_file_change(self, run_id: str, change: FileChange) -> None:
        seq = len(self.list_file_changes(run_id))
        self._db.execute(
            "INSERT INTO file_changes (run_id, seq, payload) VALUES (?,?,?)",
            (run_id, seq, change.model_dump_json()),
        )

    def list_file_changes(self, run_id: str) -> list[FileChange]:
        rows = self._db.query_all(
            "SELECT payload FROM file_changes WHERE run_id = ? ORDER BY seq ASC", (run_id,)
        )
        return [FileChange.model_validate_json(r["payload"]) for r in rows]

    # validation
    def add_validation(self, run_id: str, result: ValidationResult) -> None:
        seq = len(self.list_validation(run_id))
        self._db.execute(
            "INSERT INTO validation_results (run_id, seq, payload) VALUES (?,?,?)",
            (run_id, seq, result.model_dump_json()),
        )

    def list_validation(self, run_id: str) -> list[ValidationResult]:
        rows = self._db.query_all(
            "SELECT payload FROM validation_results WHERE run_id = ? ORDER BY seq ASC", (run_id,)
        )
        return [ValidationResult.model_validate_json(r["payload"]) for r in rows]
