import subprocess

from worktop.ai_workspace.app.ai_workspace.application.tools.base_tool import BaseTool, ToolExecutionContext
from worktop.ai_workspace.app.ai_workspace.domain.tool_definition import ToolCapabilities, ToolDefinition

# Allowlist, not a free-form shell command from the LLM — running an arbitrary string the model
# generated would be a command-injection vector. Extend this list rather than accepting
# arbitrary commands; if a repo's test command genuinely isn't here, add it explicitly.
_ALLOWED_COMMANDS: dict[str, list[str]] = {
    "npm": ["npm", "test"],
    "pytest": ["pytest"],
    "playwright": ["npx", "playwright", "test"],
}


class RunTestCommandTool(BaseTool):
    """Optional for Ask mode, enabled for Agent mode — see tool_selection_service.py. Runs a
    fixed, allowlisted command; the `command_key` argument selects which one, it is never used
    to build a shell string directly."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            id="run_test_command",
            name="Run Test Command",
            description="Run the workspace's configured test command.",
            capabilities=ToolCapabilities(reads_files=True, writes_files=False, requires_confirmation=True),
            parameters_schema={
                "type": "object",
                "properties": {"command_key": {"type": "string", "enum": list(_ALLOWED_COMMANDS)}},
                "required": ["command_key"],
            },
        )

    def execute(self, context: ToolExecutionContext, arguments: dict) -> dict:
        command_key = arguments["command_key"]
        if command_key not in _ALLOWED_COMMANDS:
            raise ValueError(f"Unknown command_key: {command_key}")

        result = subprocess.run(
            _ALLOWED_COMMANDS[command_key],
            cwd=context.workspace_path,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        return {"exit_code": result.returncode, "stdout": result.stdout[-5000:], "stderr": result.stderr[-5000:]}
