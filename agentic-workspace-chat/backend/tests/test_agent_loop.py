from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agent_context import to_converse_history, unfinished_plan
from app.tools import ToolRunner


def test_history_maps_roles_and_orders():
    messages = [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
        {"role": "user", "content": "second question"},
    ]
    result = to_converse_history(messages, limit=10, max_chars=10_000)
    assert [m["role"] for m in result] == ["user", "assistant", "user"]
    assert result[0]["content"][0]["text"] == "first question"


def test_history_merges_consecutive_same_role():
    messages = [
        {"role": "user", "content": "part one"},
        {"role": "user", "content": "part two"},
        {"role": "assistant", "content": "answer"},
    ]
    result = to_converse_history(messages, limit=10, max_chars=10_000)
    assert [m["role"] for m in result] == ["user", "assistant"]
    assert "part one" in result[0]["content"][0]["text"]
    assert "part two" in result[0]["content"][0]["text"]


def test_history_drops_leading_assistant_and_respects_budget():
    messages = [
        {"role": "assistant", "content": "orphan answer"},
        {"role": "user", "content": "x" * 300},
        {"role": "assistant", "content": "y" * 300},
    ]
    # Within budget for the last two messages only → starts at the user turn.
    result = to_converse_history(messages, limit=2, max_chars=10_000)
    assert [m["role"] for m in result] == ["user", "assistant"]

    # Budget so tight only the trailing assistant survives → dropped entirely
    # rather than sending history that starts with an assistant turn.
    tight = to_converse_history(messages, limit=10, max_chars=350)
    assert tight == []


def test_history_skips_empty_and_unknown_roles():
    messages = [
        {"role": "system", "content": "ignored"},
        {"role": "user", "content": "   "},
        {"role": "user", "content": "real"},
    ]
    result = to_converse_history(messages, limit=10, max_chars=1_000)
    assert len(result) == 1
    assert result[0]["content"][0]["text"] == "real"


def test_unfinished_plan_resumes_only_open_work():
    open_plan = [
        {"step": "one", "status": "completed"},
        {"step": "two", "status": "in_progress"},
    ]
    assert unfinished_plan(open_plan) == open_plan
    assert unfinished_plan([{"step": "one", "status": "completed"}]) == []
    assert unfinished_plan(None) == []


def _runner(tmp_path: Path, max_runs: int = 2) -> ToolRunner:
    config = SimpleNamespace(
        agent_max_command_runs=max_runs,
        workspace_max_files=100,
        workspace_max_file_bytes=1_000_000,
        custom_tool_timeout_seconds=5,
    )
    return ToolRunner(tmp_path, config)


def test_run_command_executes_allowlisted(tmp_path: Path):
    runner = _runner(tmp_path)
    result = runner.tool_run_command(["python3", "-c", "print('ok')"], 10)
    assert result["returnCode"] == 0
    assert "ok" in result["stdout"]
    assert runner.command_runs == 1


def test_run_command_budget_exhausts(tmp_path: Path):
    runner = _runner(tmp_path, max_runs=1)
    runner.tool_run_command(["python3", "-c", "print('one')"], 10)
    with pytest.raises(ValueError, match="Command budget exhausted"):
        runner.tool_run_command(["python3", "-c", "print('two')"], 10)


def test_run_command_rejects_non_allowlisted(tmp_path: Path):
    runner = _runner(tmp_path)
    result = runner.execute("run_command", {"command": ["sh", "-c", "echo bad"]})
    assert "error" in result
    assert runner.command_runs == 0
