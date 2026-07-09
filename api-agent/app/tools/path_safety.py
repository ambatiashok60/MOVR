from __future__ import annotations

from pathlib import Path

from app.errors import UnsafeWorkspacePathError


def resolve_workspace_path(repo_path: str) -> Path:
    root = Path(repo_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise UnsafeWorkspacePathError(repo_path)
    return root


def safe_join(root: Path, relative_path: str) -> Path:
    target = (root / relative_path).resolve()
    if root not in target.parents and target != root:
        raise UnsafeWorkspacePathError(str(target))
    return target
