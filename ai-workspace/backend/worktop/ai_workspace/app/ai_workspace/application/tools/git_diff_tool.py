from worktop.ai_workspace.app.ai_workspace.application.tools.base_tool import BaseTool, ToolExecutionContext
from worktop.ai_workspace.app.ai_workspace.domain.tool_definition import ToolCapabilities, ToolDefinition
from worktop.ai_workspace.app.repository.application.git_diff_service import GitDiffService


class GitDiffTool(BaseTool):
    def __init__(self, git_diff_service: GitDiffService):
        self._git_diff_service = git_diff_service

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            id="git_diff",
            name="Git Diff",
            description="Show the git diff for a file, or the whole workspace if no path is given.",
            capabilities=ToolCapabilities(reads_files=True, writes_files=False, requires_confirmation=False),
            parameters_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        )

    def execute(self, context: ToolExecutionContext, arguments: dict) -> dict:
        path = arguments.get("path")
        diff = (
            self._git_diff_service.diff_for_file(context.workspace_path, path)
            if path
            else self._git_diff_service.full_diff(context.workspace_path)
        )
        return {"diff": diff}
