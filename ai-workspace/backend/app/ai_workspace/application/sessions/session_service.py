import uuid
from datetime import datetime, timezone
from typing import Any

from app.ai_workspace.domain.chat_message import ChatMessage, ChatRole
from app.ai_workspace.domain.workspace_mode import WorkspaceMode
from app.ai_workspace.domain.workspace_session import WorkspaceSession
from app.utils.logging_utils import build_log_context, log_step


class SessionService:
    def __init__(self, store: Any):
        self._store = store

    def create_session(self, tenant_id: str, repository_path: str, branch: str, mode: WorkspaceMode) -> WorkspaceSession:
        now = datetime.now(timezone.utc)
        session = WorkspaceSession(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            repository_path=repository_path,
            branch=branch,
            mode=mode,
            current_task=None,
            started_at=now,
            last_activity_at=now,
        )
        self._store.save_session(session)
        log_step(
            "ai_workspace_session_created",
            build_log_context(
                session_id=session.id,
                tenant_id=tenant_id,
                repo_path=repository_path,
                branch=branch,
                mode=mode.value,
                stage="session",
            ),
        )
        return session

    def get_session(self, session_id: str) -> WorkspaceSession | None:
        return self._store.get_session(session_id)

    def list_sessions(self, repository_path: str | None = None) -> list[WorkspaceSession]:
        return self._store.list_sessions(repository_path)

    def touch(self, session_id: str, current_task: str | None = None) -> None:
        session = self._store.get_session(session_id)
        if not session:
            return
        session.last_activity_at = datetime.now(timezone.utc)
        if current_task is not None:
            session.current_task = current_task
        self._store.save_session(session)

    def record_message(
        self, session_id: str, role: ChatRole, content: str, execution_id: str | None = None
    ) -> ChatMessage:
        message = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc),
            execution_id=execution_id,
        )
        self._store.append_message(message)
        self.touch(session_id)
        log_step(
            "ai_workspace_message_recorded",
            build_log_context(session_id=session_id, execution_id=execution_id, stage="conversation"),
        )
        return message

    def get_messages(self, session_id: str) -> list[ChatMessage]:
        return self._store.get_messages(session_id)

    def delete_session(self, session_id: str) -> None:
        self._store.delete_session(session_id)
        log_step("ai_workspace_session_deleted", build_log_context(session_id=session_id, stage="session"))
