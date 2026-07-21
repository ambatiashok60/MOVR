"""Detect project type & whether the workspace is a git repository.

Git features are optional — a workspace need not be a repo.
"""

from __future__ import annotations

from pathlib import Path

_PROJECT_MARKERS = {
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "package.json": "node",
    "angular.json": "angular",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "go.mod": "go",
    "Cargo.toml": "rust",
}


def detect_repository(workspace: Path) -> dict:
    technologies: list[str] = []
    for marker, tech in _PROJECT_MARKERS.items():
        if (workspace / marker).exists() and tech not in technologies:
            technologies.append(tech)

    return {
        "is_git": (workspace / ".git").exists(),
        "technologies": technologies,
        "name": workspace.name,
    }
