from worktop.ai_workspace.app.repository.infrastructure.local_file_writer import LocalFileWriter


class FileWriteService:
    """Agent-mode-only. Never injected into anything Ask mode can reach — tool_selection_service.py
    is what actually enforces that boundary, but keeping the write path in its own service (as
    opposed to folding it into FileReadService) makes that boundary visible in the dependency
    graph, not just in a runtime check."""

    def __init__(self, writer: LocalFileWriter):
        self._writer = writer

    def write(self, root: str, relative_path: str, content: str) -> None:
        self._writer.write_file(root, relative_path, content)

    def delete(self, root: str, relative_path: str) -> None:
        self._writer.delete_file(root, relative_path)
