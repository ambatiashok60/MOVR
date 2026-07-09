from __future__ import annotations

from app.tools.file_reader_tool import FileReaderTool
from app.tools.path_safety import resolve_workspace_path


class FixtureScannerTool:
    def __init__(self) -> None:
        self.reader = FileReaderTool()

    def scan(self, repo_path: str) -> dict[str, list[str]]:
        root = resolve_workspace_path(repo_path)
        suffixes = (".java", ".kt", ".py", ".ts", ".js")
        fixture_files: list[str] = []
        auth_helpers: list[str] = []
        client_helpers: list[str] = []
        data_builders: list[str] = []
        base_test_classes: list[str] = []

        for relative in self.reader.list_files(repo_path, suffixes=suffixes, max_files=1600):
            lower = relative.lower()
            name = lower.rsplit("/", 1)[-1]
            if any(signal in lower for signal in ("fixture", "fixtures", "conftest", "testdata")):
                fixture_files.append(relative)
            if any(signal in lower for signal in ("auth", "token", "jwt", "security")):
                auth_helpers.append(relative)
            if any(signal in lower for signal in ("client", "request", "apihelper", "api_helper")):
                client_helpers.append(relative)
            if any(signal in lower for signal in ("builder", "factory", "mother", "fixture")):
                data_builders.append(relative)
            if name.startswith("base") and "test" in name:
                base_test_classes.append(relative)

            if relative.endswith((".java", ".py")):
                text = (root / relative).read_text(encoding="utf-8", errors="ignore")[:12000]
                lowered_text = text.lower()
                if "authorization" in lowered_text or "bearer " in lowered_text:
                    auth_helpers.append(relative)
                if "testclient" in lowered_text or "mockmvc" in lowered_text or "restassured" in lowered_text:
                    client_helpers.append(relative)
                if "@pytest.fixture" in lowered_text:
                    fixture_files.append(relative)

        return {
            "fixture_files": self._unique(fixture_files),
            "auth_helpers": self._unique(auth_helpers),
            "api_client_helpers": self._unique(client_helpers),
            "test_data_builders": self._unique(data_builders),
            "base_test_classes": self._unique(base_test_classes),
        }

    def _unique(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))[:30]
