import difflib
import hashlib
from pathlib import Path

from fastapi import HTTPException

from .config import Settings
from .models import FileChange

EXCLUDED = {".git", ".env", ".venv", "node_modules", "dist", "__pycache__"}


def resolve_workspace(raw: str, config: Settings) -> Path:
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        raise HTTPException(400, "Workspace does not exist or is not a directory")
    if not any(path.is_relative_to(root.expanduser().resolve()) for root in config.workspace_allowed_roots):
        raise HTTPException(403, "Workspace is outside WORKSPACE_ALLOWED_ROOTS")
    return path


def resolve_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or any(part in EXCLUDED for part in path.relative_to(root).parts):
        raise HTTPException(403, f"File is outside the allowed workspace: {relative}")
    return path


def files(root: Path, limit: int) -> list[str]:
    result: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if path.is_file() and not any(part in EXCLUDED for part in relative.parts):
            result.append(str(relative))
            if len(result) >= limit:
                break
    return sorted(result)


def read_text(root: Path, relative: str, max_bytes: int) -> str:
    path = resolve_file(root, relative)
    if not path.is_file() or path.stat().st_size > max_bytes:
        raise HTTPException(400, f"File is missing or exceeds {max_bytes} bytes")
    try:
        return path.read_text()
    except UnicodeDecodeError as error:
        raise HTTPException(400, "Binary files cannot be used as context") from error


def sha(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def diff_for(root: Path, change: FileChange) -> str:
    path = resolve_file(root, change.path)
    before = path.read_text() if path.exists() else ""
    after = "" if change.operation == "delete" else (change.content or "")
    return "".join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True),
        fromfile=f"a/{change.path}", tofile=f"b/{change.path}",
    ))


def apply_change(root: Path, change: FileChange) -> None:
    path = resolve_file(root, change.path)
    before = path.read_text() if path.exists() else ""
    if change.original_sha256 is not None and sha(before) != change.original_sha256:
        raise HTTPException(409, f"{change.path} changed after review")
    if change.operation == "delete":
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".agent-tmp")
    temporary.write_text(change.content or "")
    temporary.replace(path)

