import threading

from app.ai_workspace.domain.file_change import FileChange


class InMemoryReviewStore:
    """Holds proposed file changes per execution/run id until Apply is called. This is what
    makes Apply 'server-staged' — the frontend only ever sends back { run_id, kept_file_ids },
    never the generated file content itself (see ai-workspace/frontend/README.md, which flagged
    this exact question as open on the frontend side)."""

    def __init__(self):
        self._changes_by_run: dict[str, list[FileChange]] = {}
        self._lock = threading.Lock()

    def save_changes(self, run_id: str, changes: list[FileChange]) -> None:
        with self._lock:
            self._changes_by_run[run_id] = changes

    def get_changes(self, run_id: str) -> list[FileChange]:
        with self._lock:
            return list(self._changes_by_run.get(run_id, []))

    def update_decision(self, run_id: str, file_id: str, decision) -> None:
        with self._lock:
            changes = self._changes_by_run.get(run_id, [])
            for change in changes:
                if change.id == file_id:
                    change.decision = decision

    def clear(self, run_id: str) -> None:
        with self._lock:
            self._changes_by_run.pop(run_id, None)
