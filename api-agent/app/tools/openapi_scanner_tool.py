from __future__ import annotations

from app.tools.file_reader_tool import FileReaderTool


class OpenApiScannerTool:
    def __init__(self) -> None:
        self.reader = FileReaderTool()

    def scan(self, repo_path: str) -> dict[str, list[str]]:
        openapi_files: list[str] = []
        graphql_schema_files: list[str] = []
        for relative in self.reader.list_files(
            repo_path,
            suffixes=(".yaml", ".yml", ".json", ".graphql", ".graphqls"),
            max_files=1200,
        ):
            lower = relative.lower()
            if lower.endswith((".graphql", ".graphqls")):
                graphql_schema_files.append(relative)
                continue
            if any(signal in lower for signal in ("openapi", "swagger", "api-docs")):
                openapi_files.append(relative)
        return {
            "openapi_files": openapi_files[:30],
            "graphql_schema_files": graphql_schema_files[:30],
        }
