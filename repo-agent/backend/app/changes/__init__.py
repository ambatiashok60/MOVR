"""Change tracking, snapshots, and revert for agent-mode mutations."""

from app.changes.change_manager import ChangeManager
from app.changes.diff_service import unified_diff
from app.changes.snapshot_manager import SnapshotManager

__all__ = ["ChangeManager", "SnapshotManager", "unified_diff"]
