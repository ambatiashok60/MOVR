"""Registry of tool implementations keyed by tool name."""

from __future__ import annotations

from typing import Awaitable, Callable

from app.tools.base import ToolContext, ToolOutcome
from app.tools.implementations import exec_tools, read_tools, write_tools

ToolFn = Callable[[ToolContext, dict], Awaitable[ToolOutcome]]

TOOL_IMPLEMENTATIONS: dict[str, ToolFn] = {
    # read-only
    "list_directory": read_tools.list_directory,
    "get_repository_summary": read_tools.get_repository_summary,
    "search_code": read_tools.search_code,
    "read_file": read_tools.read_file,
    "read_file_range": read_tools.read_file_range,
    "find_symbol": read_tools.find_symbol,
    "find_references": read_tools.find_references,
    "detect_project_commands": read_tools.detect_project_commands,
    "inspect_git_status": read_tools.inspect_git_status,
    "inspect_git_diff": read_tools.inspect_git_diff,
    # write
    "create_file": write_tools.create_file,
    "apply_patch": write_tools.apply_patch,
    "replace_file_range": write_tools.replace_file_range,
    "move_file": write_tools.move_file,
    "delete_file": write_tools.delete_file,
    # exec
    "run_command": exec_tools.run_command,
    "run_tests": exec_tools.run_tests,
    "run_linter": exec_tools.run_linter,
    "run_type_check": exec_tools.run_type_check,
    "run_build": exec_tools.run_build,
}

__all__ = ["TOOL_IMPLEMENTATIONS", "ToolContext", "ToolOutcome", "ToolFn"]
