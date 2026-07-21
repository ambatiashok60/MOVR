from worktop.ai_workspace.app.ai_workspace.application.tools.tool_registry import ToolRegistry
from worktop.ai_workspace.app.ai_workspace.domain.workspace_mode import WorkspaceMode

# This mapping is the enforcement point for the Ask/Agent tool permission table — Ask mode
# genuinely cannot reach write_file/apply_patch/run_test_command because they're never
# returned here, not because of a runtime role check inside those tools.
_ASK_MODE_TOOL_IDS = {"read_file", "search_repository", "list_files", "git_diff"}
_AGENT_MODE_TOOL_IDS = _ASK_MODE_TOOL_IDS | {"write_file", "run_test_command"}
# apply_patch is deliberately excluded from both — it's invoked directly by review_service.py's
# apply flow, never offered to the LLM as a callable tool (see ApplyPatchTool's docstring).


class ToolSelectionService:
    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def tools_for_mode(self, mode: WorkspaceMode):
        allowed_ids = _AGENT_MODE_TOOL_IDS if mode == WorkspaceMode.AGENT else _ASK_MODE_TOOL_IDS
        return [tool for tool in self._registry.all_tools() if tool.definition.id in allowed_ids]
