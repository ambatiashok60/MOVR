"""Tool permission enforcement + core tool behaviours."""

from __future__ import annotations

import pytest

from app.models.enums import AgentMode
from app.models.tool import ToolCall
from app.tools import allowed_tools_for
from app.tools.executor import ToolExecutor
from app.tools.registry import ASK_ALLOWED_TOOLS, ToolPermissionError
from tests.conftest import run_async


def _call(name, **args):
    return ToolCall(tool_call_id="t", tool_name=name, arguments=args)


def test_ask_cannot_use_write_tools():
    assert "create_file" not in ASK_ALLOWED_TOOLS
    assert "create_file" in allowed_tools_for(AgentMode.AGENT)


def test_executor_blocks_write_tool_in_ask(workspace):
    async def go():
        with pytest.raises(ToolPermissionError):
            await ToolExecutor().execute(
                workspace=workspace, mode=AgentMode.ASK,
                tool_call=_call("create_file", path="x.txt", content="x"))
    run_async(go())


def test_search_code_finds_matches(workspace):
    async def go():
        return await ToolExecutor().execute(
            workspace=workspace, mode=AgentMode.ASK, tool_call=_call("search_code", query="status"))
    result = run_async(go())
    assert result.success and result.metadata["match_count"] >= 1


def test_path_escape_is_blocked_result(workspace):
    async def go():
        return await ToolExecutor().execute(
            workspace=workspace, mode=AgentMode.AGENT, tool_call=_call("read_file", path="../../etc/passwd"))
    result = run_async(go())
    assert not result.success and "not allowed" in result.summary.lower()


def test_apply_patch_hash_guard(workspace):
    async def go():
        ex = ToolExecutor()
        await ex.execute(workspace=workspace, mode=AgentMode.AGENT,
                         tool_call=_call("create_file", path="c.txt", content="hello"))
        return await ex.execute(workspace=workspace, mode=AgentMode.AGENT,
                                tool_call=_call("apply_patch", path="c.txt",
                                                expected_before_hash="deadbeef", new_content="bye"))
    result = run_async(go())
    assert not result.success and result.metadata.get("stale") is True
    assert (workspace / "c.txt").read_text() == "hello"  # unchanged


def test_run_command_allowlist(workspace):
    async def go():
        return await ToolExecutor().execute(
            workspace=workspace, mode=AgentMode.AGENT,
            tool_call=_call("run_command", executable="rm", arguments=["-rf", "/"]))
    result = run_async(go())
    assert not result.success and "not allowed" in result.summary.lower()
