from __future__ import annotations

from pathlib import Path

from worktop.api_agent.app.tools.path_safety import resolve_workspace_path, safe_join


class FileReaderTool:
    def read_text(self, repo_path: str, relative_path: str, max_chars: int = 20000) -> str:
        root = resolve_workspace_path(repo_path)
        target = safe_join(root, relative_path)
        text = target.read_text(encoding="utf-8", errors="ignore")
        return text[:max_chars]

    def list_files(
        self,
        repo_path: str,
        suffixes: tuple[str, ...] = (),
        max_files: int = 500,
    ) -> list[str]:
        root = resolve_workspace_path(repo_path)
        files: list[str] = []
        for path in root.rglob("*"):
            if len(files) >= max_files:
                break
            if not path.is_file() or self._skip(path):
                continue
            if suffixes and path.suffix not in suffixes:
                continue
            files.append(str(path.relative_to(root)))
        return files

    def _skip(self, path: Path) -> bool:
        skipped = {".git", "node_modules", "target", "build", "dist", ".venv", "__pycache__"}
        return any(part in skipped for part in path.parts)
