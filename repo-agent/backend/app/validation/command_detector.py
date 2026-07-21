"""Map a changed file to a fast, targeted validation action."""

from __future__ import annotations

from pathlib import Path


def validation_kind(path: str) -> str | None:
    suffix = Path(path).suffix.lower()
    if suffix == ".py":
        return "python_syntax"
    if suffix in {".ts", ".tsx", ".js", ".jsx"}:
        return "typescript"
    if suffix == ".json":
        return "json"
    return None
