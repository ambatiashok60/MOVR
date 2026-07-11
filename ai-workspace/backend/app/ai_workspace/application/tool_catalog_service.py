from app.ai_workspace.application.tools.tool_registry import ToolRegistry
from app.ai_workspace.domain.tool_definition import ToolDefinition


class ToolCatalogService:
    """Returns available tool metadata to the frontend (settings panel's tool list). Distinct
    from ToolSelectionService, which decides which tools are *usable this turn* based on mode
    — this returns everything registered, for display."""

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def list_tools(self) -> list[ToolDefinition]:
        return [tool.definition for tool in self._registry.all_tools()]
