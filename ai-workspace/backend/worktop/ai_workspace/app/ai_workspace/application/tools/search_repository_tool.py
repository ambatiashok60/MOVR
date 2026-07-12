from worktop.ai_workspace.app.ai_workspace.application.tools.base_tool import BaseTool, ToolExecutionContext
from worktop.ai_workspace.app.ai_workspace.domain.tool_definition import ToolCapabilities, ToolDefinition
from worktop.ai_workspace.app.repository.application.repository_search_service import RepositorySearchService


class SearchRepositoryTool(BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            id="search_repository",
            name="Search Repository",
            description="Search for files by name across the workspace.",
            capabilities=ToolCapabilities(reads_files=True, writes_files=False, requires_confirmation=False),
            parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        )

    def __init__(self, search_service: RepositorySearchService):
        self._search_service = search_service

    def execute(self, context: ToolExecutionContext, arguments: dict) -> dict:
        matches = self._search_service.search_by_name(context.workspace_path, arguments["query"])
        return {"matches": matches}
