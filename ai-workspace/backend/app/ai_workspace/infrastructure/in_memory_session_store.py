import threading

from app.ai_workspace.domain.chat_message import ChatMessage
from app.ai_workspace.domain.workspace_session import WorkspaceSession


class InMemorySessionStore:
    """V1 storage for sessions and their message history. Same caveat as
    InMemoryRuntimeStore — single-process, and history is lost on restart. Swap for a real
    database table once session persistence needs to survive a deploy."""

    def __init__(self):
        self._sessions: dict[str, WorkspaceSession] = {}
        self._messages: dict[str, list[ChatMessage]] = {}
        self._lock = threading.Lock()

    def save_session(self, session: WorkspaceSession) -> None:
        with self._lock:
            self._sessions[session.id] = session
            self._messages.setdefault(session.id, [])

    def get_session(self, session_id: str) -> WorkspaceSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self, repository_path: str | None = None) -> list[WorkspaceSession]:
        with self._lock:
            sessions = list(self._sessions.values())
        if repository_path:
            sessions = [s for s in sessions if s.repository_path == repository_path]
        return sorted(sessions, key=lambda s: s.last_activity_at, reverse=True)

    def append_message(self, message: ChatMessage) -> None:
        with self._lock:
            self._messages.setdefault(message.session_id, []).append(message)

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        with self._lock:
            return list(self._messages.get(session_id, []))

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
            self._messages.pop(session_id, None)
