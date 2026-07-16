from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from worktop.ai_workspace.app.ai_workspace.domain.agent_turn import AgentFileChange
from worktop.ai_workspace.app.common.path_safety import resolve_within_root

class IsolatedWorkspaceService:
    def __init__(self, root: str) -> None:
        self.root = Path(root) / "ai-workspace-isolated"

    def stage(self, execution_id: str, repository: str, changes: list[AgentFileChange]) -> str:
        target = self.root / execution_id / "worktree"
        if target.exists(): shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "worktree", "add", "--detach", str(target), "HEAD"],
            cwd=repository, capture_output=True, text=True, timeout=60, check=False,
        )
        if result.returncode != 0:
            shutil.copytree(repository, target, ignore=shutil.ignore_patterns(".git", "node_modules", ".venv", "dist", "build"))
        for change in changes:
            path = resolve_within_root(str(target), change.path)
            if change.status == "deleted":
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(change.new_content, encoding="utf-8")
        return str(target)
