import json
import re
import threading
from datetime import datetime, timezone
from typing import Any


class MySQLStateStore:
    """MySQL-backed implementation of the AI Workspace state key-value adapter.

    Requires the optional `pymysql` dependency. Configure with `AI_WORKSPACE_STATE_BACKEND=mysql`
    and the `AI_WORKSPACE_MYSQL_*` settings.
    """

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        table_name: str = "ai_workspace_state",
    ):
        try:
            import pymysql
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "PyMySQL is required for AI_WORKSPACE_STATE_BACKEND=mysql. "
                "Install the backend with the mysql extra or add pymysql to the host service."
            ) from exc

        self._pymysql = pymysql
        self._connection_args = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
            "charset": "utf8mb4",
            "autocommit": True,
        }
        self._table_name = _validate_identifier(table_name)
        self._lock = threading.Lock()
        self._initialize()

    def set(self, namespace: str, key: str, payload: dict | list) -> None:
        encoded = json.dumps(payload)
        now = datetime.now(timezone.utc).isoformat()
        sql = f"""
            INSERT INTO {self._table_name}(namespace, state_key, payload, updated_at)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE payload = VALUES(payload), updated_at = VALUES(updated_at)
        """
        with self._lock, self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, (namespace, key, encoded, now))

    def get(self, namespace: str, key: str) -> dict | list | None:
        sql = f"SELECT payload FROM {self._table_name} WHERE namespace = %s AND state_key = %s"
        with self._lock, self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, (namespace, key))
                row = cursor.fetchone()
        return json.loads(row[0]) if row else None

    def list(self, namespace: str) -> list[tuple[str, dict | list]]:
        sql = f"SELECT state_key, payload FROM {self._table_name} WHERE namespace = %s"
        with self._lock, self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, (namespace,))
                rows = cursor.fetchall()
        return [(key, json.loads(payload)) for key, payload in rows]

    def delete(self, namespace: str, key: str) -> None:
        sql = f"DELETE FROM {self._table_name} WHERE namespace = %s AND state_key = %s"
        with self._lock, self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, (namespace, key))

    def _initialize(self) -> None:
        sql = f"""
            CREATE TABLE IF NOT EXISTS {self._table_name} (
                namespace VARCHAR(128) NOT NULL,
                state_key VARCHAR(255) NOT NULL,
                payload JSON NOT NULL,
                updated_at VARCHAR(64) NOT NULL,
                PRIMARY KEY(namespace, state_key)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """
        with self._lock, self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)

    def _connect(self) -> Any:
        return self._pymysql.connect(**self._connection_args)


def _validate_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Invalid MySQL identifier: {value!r}")
    return value
