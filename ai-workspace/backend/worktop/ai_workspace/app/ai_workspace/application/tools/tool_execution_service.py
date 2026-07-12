from worktop.ai_workspace.app.ai_workspace.application.tools.base_tool import ToolExecutionContext
from worktop.ai_workspace.app.ai_workspace.application.tools.tool_registry import ToolRegistry


class ToolExecutionService:
    """The only thing that actually calls tool.execute(). Agent planning (execution_orchestrator.py
    / a future planner) decides *which* tool to call and with what arguments; this service just
    runs it and returns the result — no policy decisions live here."""

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def execute(self, tool_id: str, context: ToolExecutionContext, arguments: dict) -> dict:
        tool = self._registry.get(tool_id)
        return tool.execute(context, arguments)
