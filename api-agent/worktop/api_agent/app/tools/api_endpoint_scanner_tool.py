from __future__ import annotations

import re

from worktop.api_agent.app.schemas.repo_profile import ApiEndpointCandidate
from worktop.api_agent.app.tools.file_reader_tool import FileReaderTool
from worktop.api_agent.app.tools.path_safety import resolve_workspace_path


class ApiEndpointScannerTool:
    METHOD_PATTERN = re.compile(
        r"(?:@(Get|Post|Put|Patch|Delete|RequestMapping)\(|"
        r"\b(router|app)\.(get|post|put|patch|delete)\(|"
        r"\b(GET|POST|PUT|PATCH|DELETE)\s+['\"])",
        re.IGNORECASE,
    )
    PATH_PATTERN = re.compile(r"['\"](/[^'\"]+)['\"]")

    def __init__(self) -> None:
        self.reader = FileReaderTool()

    def scan(self, repo_path: str, max_endpoints: int = 80) -> list[ApiEndpointCandidate]:
        root = resolve_workspace_path(repo_path)
        suffixes = (".java", ".kt", ".ts", ".js", ".py", ".go", ".cs")
        endpoints: list[ApiEndpointCandidate] = []
        for relative in self.reader.list_files(repo_path, suffixes=suffixes, max_files=1200):
            if len(endpoints) >= max_endpoints:
                break
            path = root / relative
            text = path.read_text(encoding="utf-8", errors="ignore")
            if not self.METHOD_PATTERN.search(text):
                continue
            for line in text.splitlines():
                method = self._method_from_line(line)
                if method is None:
                    continue
                endpoint_path = self._path_from_line(line) or "/"
                endpoints.append(
                    ApiEndpointCandidate(
                        method=method,
                        path=endpoint_path,
                        source_file=relative,
                        service_name=self._service_name(relative),
                    )
                )
                if len(endpoints) >= max_endpoints:
                    break
        return endpoints

    def _method_from_line(self, line: str) -> str | None:
        lowered = line.lower()
        mapping = {
            "get": "GET",
            "post": "POST",
            "put": "PUT",
            "patch": "PATCH",
            "delete": "DELETE",
        }
        for key, value in mapping.items():
            if f".{key}(" in lowered or f"@{key.capitalize()}Mapping".lower() in lowered:
                return value
        if "@requestmapping" in lowered:
            for value in mapping.values():
                if value.lower() in lowered:
                    return value
            return "ANY"
        return None

    def _path_from_line(self, line: str) -> str | None:
        match = self.PATH_PATTERN.search(line)
        return match.group(1) if match else None

    def _service_name(self, relative_path: str) -> str | None:
        name = relative_path.rsplit("/", 1)[-1].split(".", 1)[0]
        return name or None
