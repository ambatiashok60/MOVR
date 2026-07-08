from dataclasses import dataclass, field

from app.ai_workspace.application.sessions.session_service import SessionService
from app.ai_workspace.domain.chat_message import ChatMessage
from app.ai_workspace.domain.workspace_runtime import WorkspaceRuntime
from app.repository.application.file_read_service import FileReadService

RECENT_MESSAGE_WINDOW = 10
MAX_FILE_CHARS = 20_000  # crude per-file ceiling until real token counting exists — see note below


@dataclass
class ContextFile:
    path: str
    content: str
    truncated: bool


@dataclass
class ContextBundle:
    workspace_path: str
    files: list[ContextFile] = field(default_factory=list)
    recent_messages: list[ChatMessage] = field(default_factory=list)


class ContextBuilderService:
    """Assembles what actually goes into a prompt: the runtime's selected files (read fresh
    from disk, not cached) plus a recent window of conversation.

    No conversation summarization yet — this only takes the last RECENT_MESSAGE_WINDOW
    messages verbatim and drops everything older, rather than compacting it into a summary.
    That matches the 'recent window' half of the context-management design discussed for the
    frontend but not the 'summary of everything before that' half — add a summarizer here
    once sessions are long enough for that gap to matter.

    MAX_FILE_CHARS is a character count, not a token count — it's a cheap safety ceiling per
    file, not a real budget. A real context_budget_manager (token-aware, provider-aware) is
    still open work, same as it was on the frontend side.
    """

    def __init__(self, file_read_service: FileReadService, session_service: SessionService):
        self._file_read_service = file_read_service
        self._session_service = session_service

    def build(self, runtime: WorkspaceRuntime) -> ContextBundle:
        files = [self._read_context_file(runtime.workspace_path, path) for path in runtime.selected_file_paths]
        messages = self._session_service.get_messages(runtime.session_id)[-RECENT_MESSAGE_WINDOW:]
        return ContextBundle(workspace_path=runtime.workspace_path, files=files, recent_messages=messages)

    def _read_context_file(self, workspace_path: str, relative_path: str) -> ContextFile:
        repo_file = self._file_read_service.read(workspace_path, relative_path)
        content = repo_file.content
        truncated = len(content) > MAX_FILE_CHARS
        if truncated:
            content = content[:MAX_FILE_CHARS]
        return ContextFile(path=relative_path, content=content, truncated=truncated)
