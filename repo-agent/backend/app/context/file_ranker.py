"""Rank candidate files by relevance to the request (keyword + convention signals)."""

from __future__ import annotations

from pathlib import Path

from app.context.repository_index import _IGNORE

_ENTRY_HINTS = ("main", "app", "index", "route", "service", "controller", "manager", "repository")


def rank_files(workspace: Path, keywords: list[str], limit: int = 8) -> list[str]:
    scored: list[tuple[int, str]] = []
    kws = [k.lower() for k in keywords]
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace)
        if any(part in _IGNORE for part in rel.parts):
            continue
        name = path.name.lower()
        score = 0
        score += sum(3 for k in kws if k and k in name)
        score += sum(1 for h in _ENTRY_HINTS if h in name)
        if path.suffix in {".py", ".ts", ".js", ".java", ".go"}:
            score += 1
        if score:
            scored.append((score, str(rel)))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [rel for _, rel in scored[:limit]]
