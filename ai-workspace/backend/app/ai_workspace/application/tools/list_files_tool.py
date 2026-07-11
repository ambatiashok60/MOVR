from app.ai_workspace.application.tools.base_tool import BaseTool, ToolExecutionContext
from app.ai_workspace.domain.tool_definition import ToolCapabilities, ToolDefinition
from app.repository.application.repository_tree_service import RepositoryTreeService


class ListFilesTool(BaseTool):
    def __init__(self, tree_service: RepositoryTreeService):
        self._tree_service = tree_service

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            id="list_files",
            name="List Files",
            description="List the repository's file tree.",
            capabilities=ToolCapabilities(reads_files=True, writes_files=False, requires_confirmation=False),
            parameters_schema={"type": "object", "properties": {}},
        )

    def execute(self, context: ToolExecutionContext, arguments: dict) -> dict:
        tree = self._tree_service.get_tree(context.workspace_path)
        return {"tree": [node.path for node in _flatten(tree)]}


def _flatten(nodes):
    for node in nodes:
        yield node
        yield from _flatten(node.children)
