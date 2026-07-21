"""Thread-safe SQLite wrapper + schema.

The whole service is a single process; SQLite in WAL mode with a short-lived
lock around writes is more than sufficient. A background run task and the
request loop may both touch the DB, so `check_same_thread=False` + a lock keep
it safe. Writes here are sub-millisecond, so we call synchronously.
"""

from __future__ import annotations

import sqlite3
import threading
from functools import lru_cache
from typing import Any, Iterable

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    workspace_path TEXT NOT NULL,
    title TEXT NOT NULL,
    mode TEXT NOT NULL,
    turn_count INTEGER NOT NULL DEFAULT 0,
    compaction_count INTEGER NOT NULL DEFAULT 0,
    active_summary_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    run_id TEXT,
    turn_index INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);

CREATE TABLE IF NOT EXISTS conversation_summaries (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    workspace_path TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    agent_state TEXT,
    client_request_id TEXT UNIQUE,
    last_event_sequence INTEGER NOT NULL DEFAULT 0,
    plan_revision INTEGER NOT NULL DEFAULT 0,
    tool_call_count INTEGER NOT NULL DEFAULT 0,
    files_read_count INTEGER NOT NULL DEFAULT 0,
    files_modified_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_activity_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_conv ON agent_runs(conversation_id);

CREATE TABLE IF NOT EXISTS run_events (
    run_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (run_id, sequence)
);

CREATE TABLE IF NOT EXISTS run_plans (
    run_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS response_batches (
    run_id TEXT NOT NULL,
    batch_index INTEGER NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (run_id, batch_index)
);

CREATE TABLE IF NOT EXISTS file_changes (
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (run_id, seq)
);

CREATE TABLE IF NOT EXISTS validation_results (
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (run_id, seq)
);
"""


class Database:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._lock = threading.RLock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        with self._lock:
            self._conn.execute(sql, tuple(params))
            self._conn.commit()

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            return cur.fetchone()

    def query_all(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            return cur.fetchall()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


@lru_cache
def get_database() -> Database:
    return Database(settings.database_path)
