import threading

from worktop.ai_workspace.app.ai_workspace.domain.workspace_runtime import WorkspaceRuntime


class InMemoryRuntimeStore:
    """V1 storage for active workspace runtimes, keyed by session id. Single-process only —
    fine for a beta with one backend instance, but breaks the moment the backend scales
    horizontally. Swap for Redis (same interface: get/set/delete by session id) when that
    becomes true; nothing above this class should need to change."""

    def __init__(self):
        self._runtimes: dict[str, WorkspaceRuntime] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> WorkspaceRuntime | None:
        with self._lock:
            return self._runtimes.get(session_id)

    def set(self, runtime: WorkspaceRuntime) -> None:
        with self._lock:
            self._runtimes[runtime.session_id] = runtime

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._runtimes.pop(session_id, None)
