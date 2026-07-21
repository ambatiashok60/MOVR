"""Write tools (Agent mode only). Each verifies content before mutating and
reports a structured file-change in `metadata['file_change']` so the change
manager can snapshot, diff, and revert.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.tools.base import ToolContext, ToolOutcome


def _hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _change(path: str, change_type: str, before: str | None, after: str | None) -> dict:
    return {
        "path": path,
        "change_type": change_type,
        "before_hash": _hash(before) if before is not None else None,
        "after_hash": _hash(after) if after is not None else None,
        "before_content": before,
        "after_content": after,
    }


async def create_file(ctx: ToolContext, args: dict) -> ToolOutcome:
    rel = args.get("path", "")
    target = ctx.path_guard.resolve_inside_workspace(ctx.workspace, rel)
    content = str(args.get("content", ""))
    overwrite = bool(args.get("overwrite", False))
    existed = target.exists()
    if existed and not overwrite:
        return ToolOutcome(False, f"{rel} already exists (pass overwrite=true)")
    before = _read(target) if existed else None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    change = _change(rel, "modified" if existed else "created", before, content)
    return ToolOutcome(True, f"{'Updated' if existed else 'Created'} {rel}", None, {"file_change": change})


async def apply_patch(ctx: ToolContext, args: dict) -> ToolOutcome:
    rel = args.get("path", "")
    target = ctx.path_guard.resolve_inside_workspace(ctx.workspace, rel)
    if not target.exists() or not target.is_file():
        return ToolOutcome(False, f"File not found: {rel}")
    before = _read(target)
    if before is None:
        return ToolOutcome(False, f"Cannot read {rel} as text")

    expected = args.get("expected_before_hash")
    if expected and expected != _hash(before):
        # Stale context: the file changed since the model read it.
        return ToolOutcome(False, f"expected_before_hash mismatch for {rel}; re-read the file",
                           None, {"stale": True})

    if "new_content" in args:
        after = str(args["new_content"])
    elif "find" in args:
        find = str(args["find"])
        if find not in before:
            return ToolOutcome(False, f"'find' text not present in {rel}")
        after = before.replace(find, str(args.get("replace", "")), 1)
    else:
        return ToolOutcome(False, "apply_patch requires 'new_content' or 'find'/'replace'")

    target.write_text(after, encoding="utf-8")
    return ToolOutcome(True, f"Patched {rel}", None, {"file_change": _change(rel, "modified", before, after)})


async def replace_file_range(ctx: ToolContext, args: dict) -> ToolOutcome:
    rel = args.get("path", "")
    target = ctx.path_guard.resolve_inside_workspace(ctx.workspace, rel)
    before = _read(target)
    if before is None:
        return ToolOutcome(False, f"File not found or unreadable: {rel}")
    start = max(1, int(args.get("start", 1)))
    end = int(args.get("end", start))
    replacement = str(args.get("content", ""))
    lines = before.splitlines()
    new_lines = lines[:start - 1] + replacement.splitlines() + lines[end:]
    after = "\n".join(new_lines) + ("\n" if before.endswith("\n") else "")
    target.write_text(after, encoding="utf-8")
    return ToolOutcome(True, f"Replaced lines {start}-{end} in {rel}", None,
                       {"file_change": _change(rel, "modified", before, after)})


async def move_file(ctx: ToolContext, args: dict) -> ToolOutcome:
    src_rel, dst_rel = args.get("src", ""), args.get("dst", "")
    src = ctx.path_guard.resolve_inside_workspace(ctx.workspace, src_rel)
    dst = ctx.path_guard.resolve_inside_workspace(ctx.workspace, dst_rel)
    if not src.exists():
        return ToolOutcome(False, f"Source not found: {src_rel}")
    before = _read(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    return ToolOutcome(True, f"Moved {src_rel} -> {dst_rel}", None,
                       {"file_change": _change(dst_rel, "moved", before, before)})


async def delete_file(ctx: ToolContext, args: dict) -> ToolOutcome:
    rel = args.get("path", "")
    target = ctx.path_guard.resolve_inside_workspace(ctx.workspace, rel)
    if not target.exists():
        return ToolOutcome(False, f"File not found: {rel}")
    before = _read(target)
    target.unlink()
    return ToolOutcome(True, f"Deleted {rel}", None,
                       {"file_change": _change(rel, "deleted", before, None)})
