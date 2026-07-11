from typing import Any

from app.ai_workspace.domain.workspace_mode import WorkspaceMode
from app.ai_workspace.domain.workspace_runtime import WorkspaceRuntime


class WorkspaceRuntimeService:
    """Owns the mutable per-session runtime: which workspace path, which files are selected,
    which model/tools are active, current mode. Distinct from WorkspaceSession (session_service.py)
    — the session is what's listed in history; the runtime is what's live right now for that
    session and is dropped when the store is cleared (see InMemoryRuntimeStore's caveats)."""

    def __init__(self, store: Any):
        self._store = store

    def start(self, session_id: str, workspace_path: str, mode: WorkspaceMode) -> WorkspaceRuntime:
        runtime = WorkspaceRuntime(workspace_path=workspace_path, session_id=session_id, mode=mode)
        self._store.set(runtime)
        return runtime

    def get(self, session_id: str) -> WorkspaceRuntime | None:
        return self._store.get(session_id)

    def set_mode(self, session_id: str, mode: WorkspaceMode) -> None:
        runtime = self._store.get(session_id)
        if runtime:
            runtime.mode = mode
            self._store.set(runtime)

    def set_selected_files(self, session_id: str, file_paths: list[str]) -> None:
        runtime = self._store.get(session_id)
        if runtime:
            runtime.selected_file_paths = file_paths
            self._store.set(runtime)

    def set_selected_model(self, session_id: str, model_id: str) -> None:
        runtime = self._store.get(session_id)
        if runtime:
            runtime.selected_model_id = model_id
            self._store.set(runtime)

    def stop(self, session_id: str) -> None:
        self._store.delete(session_id)
