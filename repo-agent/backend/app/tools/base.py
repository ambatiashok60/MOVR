"""Shared types for tool implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.workspace.path_guard import PathGuard


@dataclass
class ToolContext:
    workspace: Path
    path_guard: PathGuard = field(default_factory=PathGuard)


@dataclass
class ToolOutcome:
    success: bool
    summary: str
    content: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
