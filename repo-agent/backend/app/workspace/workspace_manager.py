"""The only component allowed to establish a repository root.

Never trust a workspace path just because the frontend sent it — resolve and
validate it here before any file operation.
"""

from __future__ import annotations

from pathlib import Path


class WorkspaceError(ValueError):
    pass


class WorkspaceManager:
    def open_workspace(self, raw_path: str) -> Path:
        if not raw_path or not raw_path.strip():
            raise WorkspaceError("Workspace path is required")

        workspace = Path(raw_path).expanduser().resolve()

        if not workspace.exists():
            raise WorkspaceError(f"Workspace does not exist: {workspace}")
        if not workspace.is_dir():
            raise WorkspaceError(f"Workspace must be a directory: {workspace}")

        return workspace
