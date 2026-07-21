from worktop.ai_workspace.app.ai_workspace.application.tools.tool_execution_service import ToolExecutionService
from worktop.ai_workspace.app.ai_workspace.application.tools.tool_registry import ToolRegistry
from worktop.ai_workspace.app.ai_workspace.application.tools.tool_selection_service import ToolSelectionService
from worktop.ai_workspace.app.dependencies.container import container


def get_tool_registry() -> ToolRegistry:
    return container.tool_registry


def get_tool_selection_service() -> ToolSelectionService:
    return ToolSelectionService(container.tool_registry)


def get_tool_execution_service() -> ToolExecutionService:
    return ToolExecutionService(container.tool_registry)
