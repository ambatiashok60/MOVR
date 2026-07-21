import difflib
import hashlib
from pathlib import Path

from fastapi import HTTPException

from .config import Settings
from .models import FileChange

EXCLUDED = {
    ".git", ".env", ".venv", "node_modules", "dist", "build", "__pycache__",
    ".DS_Store", ".ruff_cache", ".pytest_cache", ".angular", ".cache", "coverage",
}
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz", ".tar",
    ".7z", ".rar", ".woff", ".woff2", ".ttf", ".otf", ".mp3", ".mp4", ".mov", ".avi",
    ".db", ".sqlite", ".pyc", ".dll", ".so", ".dylib", ".class", ".jar", ".exe", ".bin",
}


def is_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        return b"\x00" in path.open("rb").read(4096)
    except OSError:
        return True


def resolve_workspace(raw: str, config: Settings) -> Path:
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise HTTPException(400, "Workspace path does not exist")
    if not path.is_dir():
        raise HTTPException(400, "Workspace path is not a directory")
    if not any(path.is_relative_to(root.expanduser().resolve()) for root in config.workspace_allowed_roots):
        raise HTTPException(403, "Workspace is outside WORKSPACE_ALLOWED_ROOTS")
    return path


def resolve_file(root: Path, relative: str) -> Path:
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or any(part in EXCLUDED for part in path.relative_to(root).parts):
        raise HTTPException(403, f"File is outside the allowed workspace: {relative}")
    return path


def files(root: Path, limit: int) -> list[str]:
    result: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if path.is_file() and not is_binary(path) and not any(part in EXCLUDED for part in relative.parts):
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

def diff_hunks(diff: str) -> list[dict]:
    lines = diff.splitlines()
    hunks, current = [], None
    for line in lines:
        if line.startswith('@@'):
            if current: hunks.append(current)
            current = {"id": f"hunk-{len(hunks) + 1}", "header": line, "lines": []}
        elif current is not None:
            current["lines"].append(line)
    if current: hunks.append(current)
    return hunks

def apply_hunks(before: str, diff: str, accepted: set[str]) -> str:
    source = before.splitlines(True)
    output, cursor, index = [], 0, 0
    for hunk in diff_hunks(diff):
        index += 1
        header = hunk["header"].split()
        old = next((part for part in header if part.startswith('-')), '-1,0')[1:]
        start = int(old.split(',')[0]) - 1
        output.extend(source[cursor:start]); cursor = start
        if hunk["id"] not in accepted:
            count = int(old.split(',')[1]) if ',' in old else 1
            output.extend(source[cursor:cursor + count]); cursor += count
            continue
        for line in hunk["lines"]:
            if line.startswith(' '): output.append(line[1:] + ('\n' if not line[1:].endswith('\n') else '')); cursor += 1
            elif line.startswith('-'): cursor += 1
            elif line.startswith('+'): output.append(line[1:] + ('\n' if not line[1:].endswith('\n') else ''))
    output.extend(source[cursor:])
    return ''.join(output)


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
