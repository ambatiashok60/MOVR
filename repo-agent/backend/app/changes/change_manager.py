"""Records file changes from tool results, computes diffs, and reverts a run."""

from __future__ import annotations

from pathlib import Path

from app.changes.diff_service import unified_diff
from app.changes.snapshot_manager import SnapshotManager
from app.models.changes import FileChange
from app.models.tool import ToolResult
from app.persistence.repositories import RunArtifactRepository
from app.workspace.path_guard import PathGuard


class ChangeManager:
    def __init__(self, artifacts: RunArtifactRepository, snapshots: SnapshotManager) -> None:
        self._artifacts = artifacts
        self._snapshots = snapshots
        self._path_guard = PathGuard()
        # Keep before/after content in memory per run for revert.
        self._content: dict[str, dict[str, str | None]] = {}

    def record_from_tool(self, run_id: str, result: ToolResult,
                         plan_step_id: str | None = None) -> FileChange | None:
        raw = result.metadata.get("file_change")
        if not raw:
            return None

        before = raw.get("before_content")
        after = raw.get("after_content")
        change = FileChange(
            path=raw["path"], change_type=raw["change_type"],
            before_hash=raw.get("before_hash"), after_hash=raw.get("after_hash"),
            diff=unified_diff(raw["path"], before, after),
            plan_step_id=plan_step_id, tool_call_id=result.tool_call_id,
        )
        self._artifacts.add_file_change(run_id, change)
        self._content.setdefault(run_id, {})[change.path] = before
        return change

    def revert(self, run_id: str, workspace: Path) -> list[str]:
        """Restore recorded files to their pre-run content. Returns reverted paths."""
        reverted: list[str] = []
        for change in reversed(self._artifacts.list_file_changes(run_id)):
            before = self._content.get(run_id, {}).get(change.path)
            target = self._path_guard.resolve_inside_workspace(workspace, change.path)
            if change.change_type == "created":
                if target.exists():
                    target.unlink()
                    reverted.append(change.path)
            elif before is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(before, encoding="utf-8")
                reverted.append(change.path)
        return reverted
