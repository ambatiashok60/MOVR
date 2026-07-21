"""Read-only tools. None of these mutate the workspace."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.config import settings
from app.tools.base import ToolContext, ToolOutcome
from app.workspace.repository_detector import detect_repository

_IGNORE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
                ".mypy_cache", ".pytest_cache", ".angular", "coverage"}
_BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".tar",
               ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mov", ".class", ".jar", ".so",
               ".dylib", ".pyc", ".db", ".sqlite"}


def _iter_text_files(root: Path, max_files: int = 4000):
    count = 0
    for path in sorted(root.rglob("*")):
        if count >= max_files:
            return
        if path.is_dir():
            continue
        if any(part in _IGNORE_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in _BINARY_EXT:
            continue
        count += 1
        yield path


async def list_directory(ctx: ToolContext, args: dict) -> ToolOutcome:
    target = ctx.path_guard.resolve_inside_workspace(ctx.workspace, args.get("path", "."))
    depth = int(args.get("depth", 1))
    if not target.exists() or not target.is_dir():
        return ToolOutcome(False, f"Not a directory: {args.get('path', '.')}")

    lines: list[str] = []
    base_depth = len(target.parts)
    for path in sorted(target.rglob("*")):
        rel_parts = path.relative_to(target).parts
        if any(part in _IGNORE_DIRS for part in rel_parts):
            continue
        if len(path.parts) - base_depth > depth:
            continue
        indent = "  " * (len(path.parts) - base_depth - 1)
        marker = "/" if path.is_dir() else ""
        lines.append(f"{indent}{path.name}{marker}")
        if len(lines) >= 500:
            break
    return ToolOutcome(True, f"{len(lines)} entries under {args.get('path', '.')}",
                       "\n".join(lines), {"entry_count": len(lines)})


async def get_repository_summary(ctx: ToolContext, args: dict) -> ToolOutcome:
    info = detect_repository(ctx.workspace)
    top = [p.name + ("/" if p.is_dir() else "")
           for p in sorted(ctx.workspace.iterdir()) if p.name not in _IGNORE_DIRS][:60]
    content = (f"Name: {info['name']}\nGit: {info['is_git']}\n"
               f"Technologies: {', '.join(info['technologies']) or 'unknown'}\n\n"
               "Top level:\n" + "\n".join(top))
    return ToolOutcome(True, f"{info['name']} ({', '.join(info['technologies']) or 'unknown'})",
                       content, {"repository": info})


async def search_code(ctx: ToolContext, args: dict) -> ToolOutcome:
    query = str(args.get("query", "")).strip()
    if not query:
        return ToolOutcome(False, "search_code requires a 'query'")
    limit = int(args.get("limit", settings.max_search_results_per_batch))
    matches: list[str] = []
    files_hit: set[str] = set()
    for path in _iter_text_files(ctx.workspace):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if query.lower() in line.lower():
                rel = path.relative_to(ctx.workspace)
                files_hit.add(str(rel))
                matches.append(f"{rel}:{lineno}: {line.strip()[:160]}")
                if len(matches) >= limit:
                    break
        if len(matches) >= limit:
            break
    summary = f"Found {len(matches)} matches across {len(files_hit)} files"
    return ToolOutcome(True, summary, "\n".join(matches),
                       {"files": sorted(files_hit), "match_count": len(matches)})


async def read_file(ctx: ToolContext, args: dict) -> ToolOutcome:
    target = ctx.path_guard.resolve_inside_workspace(ctx.workspace, args.get("path", ""))
    if not target.exists() or not target.is_file():
        return ToolOutcome(False, f"File not found: {args.get('path')}")
    text = target.read_text(encoding="utf-8", errors="ignore")
    return ToolOutcome(True, f"Read {args.get('path')} ({len(text)} chars)", text,
                       {"path": args.get("path"), "chars": len(text)})


async def read_file_range(ctx: ToolContext, args: dict) -> ToolOutcome:
    target = ctx.path_guard.resolve_inside_workspace(ctx.workspace, args.get("path", ""))
    if not target.exists() or not target.is_file():
        return ToolOutcome(False, f"File not found: {args.get('path')}")
    start = max(1, int(args.get("start", 1)))
    end = int(args.get("end", start + 50))
    lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
    selected = lines[start - 1:end]
    body = "\n".join(f"{start + i}\t{ln}" for i, ln in enumerate(selected))
    return ToolOutcome(True, f"Read {args.get('path')} lines {start}-{end}", body,
                       {"path": args.get("path"), "start": start, "end": end})


async def find_symbol(ctx: ToolContext, args: dict) -> ToolOutcome:
    name = str(args.get("name", "")).strip()
    if not name:
        return ToolOutcome(False, "find_symbol requires a 'name'")
    prefixes = ("def ", "class ", "function ", "func ", "const ", "let ", "var ", "interface ", "type ")
    hits: list[str] = []
    for path in _iter_text_files(ctx.workspace):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if name in stripped and stripped.startswith(prefixes):
                hits.append(f"{path.relative_to(ctx.workspace)}:{lineno}: {stripped[:160]}")
                if len(hits) >= 50:
                    break
        if len(hits) >= 50:
            break
    return ToolOutcome(True, f"{len(hits)} definitions for '{name}'", "\n".join(hits),
                       {"symbol": name, "count": len(hits)})


async def find_references(ctx: ToolContext, args: dict) -> ToolOutcome:
    args = {"query": args.get("name", args.get("query", ""))}
    outcome = await search_code(ctx, args)
    outcome.summary = outcome.summary.replace("matches", "references")
    return outcome


async def detect_project_commands(ctx: ToolContext, args: dict) -> ToolOutcome:
    info = detect_repository(ctx.workspace)
    commands: dict[str, list[str]] = {}
    if "python" in info["technologies"]:
        commands["test"] = ["python", "-m", "pytest", "-q"]
        commands["lint"] = ["ruff", "check", "."]
        commands["type_check"] = ["mypy", "."]
    if "node" in info["technologies"] or "angular" in info["technologies"]:
        commands["test"] = ["npm", "test"]
        commands["build"] = ["npm", "run", "build"]
        commands["lint"] = ["npm", "run", "lint"]
    if "maven" in info["technologies"]:
        commands["build"] = ["mvn", "-q", "compile"]
        commands["test"] = ["mvn", "-q", "test"]
    content = "\n".join(f"{k}: {' '.join(v)}" for k, v in commands.items()) or "none detected"
    return ToolOutcome(True, f"{len(commands)} command groups detected", content,
                       {"commands": commands, "technologies": info["technologies"]})


async def _git(ctx: ToolContext, subargs: list[str]) -> ToolOutcome:
    if not (ctx.workspace / ".git").exists():
        return ToolOutcome(True, "Not a git repository", "")
    proc = await asyncio.create_subprocess_exec(
        "git", *subargs, cwd=str(ctx.workspace),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    text = (out or err).decode(errors="replace")
    return ToolOutcome(proc.returncode == 0, f"git {' '.join(subargs)}", text[:20000])


async def inspect_git_status(ctx: ToolContext, args: dict) -> ToolOutcome:
    return await _git(ctx, ["status", "--short", "--branch"])


async def inspect_git_diff(ctx: ToolContext, args: dict) -> ToolOutcome:
    return await _git(ctx, ["diff", "--stat"])
