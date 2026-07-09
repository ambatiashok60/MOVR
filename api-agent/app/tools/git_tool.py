from __future__ import annotations

import subprocess

from app.tools.path_safety import resolve_workspace_path


class GitTool:
    def current_branch(self, repo_path: str) -> str | None:
        root = resolve_workspace_path(repo_path)
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        branch = result.stdout.strip()
        return branch or None

    def changed_files(self, repo_path: str) -> list[str]:
        root = resolve_workspace_path(repo_path)
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
