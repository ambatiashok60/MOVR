"""Captures a run's starting point before the first mutation.

Git repos: record branch/HEAD/status. Non-git: rely on per-change
before_content captured by the write tools (used by ChangeManager.revert).
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class SnapshotManager:
    def __init__(self) -> None:
        self._snapshots: dict[str, dict] = {}

    def snapshot(self, run_id: str, workspace: Path) -> dict:
        if run_id in self._snapshots:
            return self._snapshots[run_id]
        is_git = (workspace / ".git").exists()
        snapshot: dict = {"is_git": is_git, "workspace": str(workspace)}
        if is_git:
            snapshot["branch"] = self._git(workspace, ["rev-parse", "--abbrev-ref", "HEAD"])
            snapshot["head"] = self._git(workspace, ["rev-parse", "HEAD"])
            snapshot["status"] = self._git(workspace, ["status", "--short"])
        self._snapshots[run_id] = snapshot
        return snapshot

    @staticmethod
    def _git(workspace: Path, args: list[str]) -> str:
        try:
            out = subprocess.run(["git", *args], cwd=str(workspace),
                                 capture_output=True, text=True, timeout=10)
            return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
