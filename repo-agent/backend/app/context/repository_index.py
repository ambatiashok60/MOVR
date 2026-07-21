"""A lazily-built, lightweight summary of the workspace used for planning."""

from __future__ import annotations

from pathlib import Path

from app.workspace.repository_detector import detect_repository

_IGNORE = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".angular"}


class RepositoryIndex:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._summary: dict | None = None

    @property
    def summary(self) -> dict:
        if self._summary is None:
            self._summary = self._build()
        return self._summary

    def _build(self) -> dict:
        info = detect_repository(self.workspace)
        top = [p.name + ("/" if p.is_dir() else "")
               for p in sorted(self.workspace.iterdir()) if p.name not in _IGNORE][:40]
        return {
            "name": info["name"],
            "is_git": info["is_git"],
            "technologies": info["technologies"],
            "top_level": top,
        }
