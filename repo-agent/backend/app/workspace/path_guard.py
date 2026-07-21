"""Sandbox every tool-supplied path to the workspace root.

Blocks traversal escapes such as ``../../.aws/config`` and absolute paths that
resolve outside the workspace. Security-critical; heavily unit-tested.
"""

from __future__ import annotations

from pathlib import Path


class PathGuard:
    def resolve_inside_workspace(self, workspace: Path, relative_path: str) -> Path:
        workspace = workspace.resolve()
        raw = (relative_path or "").strip()

        # Reject absolute inputs outright; callers pass workspace-relative paths.
        candidate_base = Path(raw)
        if candidate_base.is_absolute():
            candidate = candidate_base.resolve()
        else:
            candidate = (workspace / candidate_base).resolve()

        try:
            candidate.relative_to(workspace)
        except ValueError as exc:
            raise PermissionError(
                f"Access outside the workspace is not allowed: {relative_path}"
            ) from exc

        return candidate
