from app.ai_workspace.application.tools.base_tool import BaseTool


class ToolRegistry:
    """Flat lookup of every registered tool by id. Populated once at startup by
    tool_dependencies.py — nothing else constructs tool instances directly."""

    def __init__(self, tools: list[BaseTool]):
        self._tools_by_id = {tool.definition.id: tool for tool in tools}

    def get(self, tool_id: str) -> BaseTool:
        if tool_id not in self._tools_by_id:
            raise KeyError(f"Unknown tool id: {tool_id}")
        return self._tools_by_id[tool_id]

    def all_tools(self) -> list[BaseTool]:
        return list(self._tools_by_id.values())
