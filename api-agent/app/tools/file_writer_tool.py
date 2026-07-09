from __future__ import annotations

from pathlib import Path

from app.schemas.generated_file import GeneratedFile
from app.tools.path_safety import resolve_workspace_path, safe_join


class FileWriterTool:
    def write_text(
        self,
        repo_path: str,
        relative_path: str,
        content: str,
        test_target: str,
        summary: str,
    ) -> GeneratedFile:
        root = resolve_workspace_path(repo_path)
        target = safe_join(root, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        operation = "updated" if target.exists() else "created"
        target.write_text(content, encoding="utf-8")
        return GeneratedFile(
            path=str(target.relative_to(root)),
            operation=operation,
            test_target=test_target,
            summary=summary,
        )
