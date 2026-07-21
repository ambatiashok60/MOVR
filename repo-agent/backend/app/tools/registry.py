"""Tool definitions + mode permission map.

The executor rejects any tool not permitted for the active mode, even if the
model requests it.
"""

from __future__ import annotations

from app.models.enums import AgentMode
from app.models.tool import ToolDefinition

_ASK = {AgentMode.ASK, AgentMode.AGENT}
_AGENT_ONLY = {AgentMode.AGENT}


class ToolPermissionError(PermissionError):
    pass


_DEFINITIONS: dict[str, ToolDefinition] = {}


def _register(name: str, description: str, allowed_modes: set[AgentMode],
              *, mutates: bool = False, timeout: int = 120) -> None:
    _DEFINITIONS[name] = ToolDefinition(
        name=name, description=description, allowed_modes=allowed_modes,
        timeout_seconds=timeout, mutates_workspace=mutates,
    )


# --- read-only (available in both Ask and Agent) --------------------------
_register("list_directory", "List entries under a workspace directory", _ASK)
_register("get_repository_summary", "Summarize repo type and top-level layout", _ASK)
_register("search_code", "Search file contents for a query", _ASK)
_register("read_file", "Read a whole file (bounded)", _ASK)
_register("read_file_range", "Read a line range of a file", _ASK)
_register("find_symbol", "Find a symbol definition", _ASK)
_register("find_references", "Find references to a symbol", _ASK)
_register("detect_project_commands", "Detect build/test/lint commands", _ASK)
_register("inspect_git_status", "Show git status (if a repo)", _ASK)
_register("inspect_git_diff", "Show git diff (if a repo)", _ASK)

# --- write (Agent only) ----------------------------------------------------
_register("create_file", "Create or overwrite a file", _AGENT_ONLY, mutates=True)
_register("apply_patch", "Apply a hash-guarded edit to a file", _AGENT_ONLY, mutates=True)
_register("replace_file_range", "Replace a line range of a file", _AGENT_ONLY, mutates=True)
_register("move_file", "Move/rename a file", _AGENT_ONLY, mutates=True)
_register("delete_file", "Delete a file", _AGENT_ONLY, mutates=True)

# --- execution (Agent only) -----------------------------------------------
_register("run_command", "Run an allowlisted command", _AGENT_ONLY, mutates=True)
_register("run_tests", "Run the project's tests", _AGENT_ONLY, mutates=True)
_register("run_linter", "Run the project's linter", _AGENT_ONLY, mutates=True)
_register("run_type_check", "Run the project's type checker", _AGENT_ONLY, mutates=True)
_register("run_build", "Run the project's build", _AGENT_ONLY, mutates=True)


ASK_ALLOWED_TOOLS = frozenset(n for n, d in _DEFINITIONS.items() if AgentMode.ASK in d.allowed_modes)
AGENT_ALLOWED_TOOLS = frozenset(_DEFINITIONS.keys())


def allowed_tools_for(mode: AgentMode) -> frozenset[str]:
    return ASK_ALLOWED_TOOLS if mode == AgentMode.ASK else AGENT_ALLOWED_TOOLS


def get_tool_definition(name: str) -> ToolDefinition | None:
    return _DEFINITIONS.get(name)


def list_tool_definitions() -> list[ToolDefinition]:
    return list(_DEFINITIONS.values())
