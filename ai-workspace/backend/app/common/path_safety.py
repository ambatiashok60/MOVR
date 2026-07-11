from pathlib import Path


class PathEscapesWorkspaceError(ValueError):
    """Raised when a requested relative path would resolve outside the workspace root —
    the one check every tool that reads or writes by path must go through, since the path
    ultimately comes from an LLM tool call, not a trusted caller."""


def resolve_within_root(root: str, relative_path: str) -> Path:
    root_path = Path(root).resolve()
    candidate = (root_path / relative_path).resolve()

    if candidate != root_path and root_path not in candidate.parents:
        raise PathEscapesWorkspaceError(f"'{relative_path}' resolves outside workspace root '{root}'")

    return candidate
