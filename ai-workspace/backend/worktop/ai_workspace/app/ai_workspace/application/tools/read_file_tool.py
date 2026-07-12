from worktop.ai_workspace.app.ai_workspace.application.tools.base_tool import BaseTool, ToolExecutionContext
from worktop.ai_workspace.app.ai_workspace.domain.tool_definition import ToolCapabilities, ToolDefinition
from worktop.ai_workspace.app.repository.application.file_read_service import FileReadService


class ReadFileTool(BaseTool):
    def __init__(self, file_read_service: FileReadService):
        self._file_read_service = file_read_service

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            id="read_file",
            name="Read File",
            description="Read the content of a single file in the workspace.",
            capabilities=ToolCapabilities(reads_files=True, writes_files=False, requires_confirmation=False),
            parameters_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        )

    def execute(self, context: ToolExecutionContext, arguments: dict) -> dict:
        repo_file = self._file_read_service.read(context.workspace_path, arguments["path"])
        return {"path": repo_file.metadata.path, "content": repo_file.content}
