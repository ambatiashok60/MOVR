from app.ai_workspace.application.tools.base_tool import BaseTool, ToolExecutionContext
from app.ai_workspace.domain.tool_definition import ToolCapabilities, ToolDefinition
from app.repository.application.file_write_service import FileWriteService


class WriteFileTool(BaseTool):
    """Agent-mode-only — tool_selection_service.py never includes this in Ask mode's tool set.
    Writes go straight to disk when this tool runs; the review/keep-reject step happens
    *before* the agent turn calls this tool (the LLM proposes changes, review_service.py
    stages them, and only apply_patch_tool.py — not this tool — writes kept files after
    review). This tool exists for cases where the agent needs to write scratch/intermediate
    files as part of its own reasoning, not for the primary file-change proposal path."""

    def __init__(self, file_write_service: FileWriteService):
        self._file_write_service = file_write_service

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            id="write_file",
            name="Write File",
            description="Write content to a file in the workspace.",
            capabilities=ToolCapabilities(reads_files=False, writes_files=True, requires_confirmation=True),
            parameters_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        )

    def execute(self, context: ToolExecutionContext, arguments: dict) -> dict:
        self._file_write_service.write(context.workspace_path, arguments["path"], arguments["content"])
        return {"path": arguments["path"], "written": True}
