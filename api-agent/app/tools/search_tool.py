from __future__ import annotations

from app.tools.file_reader_tool import FileReaderTool
from app.tools.path_safety import resolve_workspace_path


class SearchTool:
    def __init__(self) -> None:
        self.reader = FileReaderTool()

    def search(
        self,
        repo_path: str,
        patterns: list[str],
        suffixes: tuple[str, ...] = (),
        max_matches: int = 100,
    ) -> list[str]:
        root = resolve_workspace_path(repo_path)
        matches: list[str] = []
        for relative in self.reader.list_files(repo_path, suffixes=suffixes, max_files=1000):
            if len(matches) >= max_matches:
                break
            path = root / relative
            text = path.read_text(encoding="utf-8", errors="ignore")
            lowered = text.lower()
            if any(pattern.lower() in lowered for pattern in patterns):
                matches.append(relative)
        return matches
