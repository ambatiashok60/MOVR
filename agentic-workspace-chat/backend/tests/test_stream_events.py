from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

from app.bedrock import Bedrock
from app.workflows import classify_request


def test_agent_emits_plan_text_usage_and_activity_events(tmp_path: Path, monkeypatch):
    config = SimpleNamespace(
        agent_history_messages=12, agent_history_max_chars=24_000,
        agent_max_response_continuations=1, agent_state_dir=tmp_path / "state",
        workspace_max_files=100, workspace_max_file_bytes=100_000,
        custom_tool_timeout_seconds=5, agent_max_command_runs=2,
        bedrock_model_id="test-model", bedrock_max_tokens=1000,
    )
    client = Mock()
    client.converse.return_value = {
        "output": {"message": {"role": "assistant", "content": [{"text": "Hello from the agent"}]}},
        "usage": {"inputTokens": 12, "outputTokens": 5, "totalTokens": 17},
        "stopReason": "end_turn",
    }
    bedrock = Bedrock(config)
    monkeypatch.setattr(bedrock, "_client", Mock(return_value=client))
    events = []

    result = bedrock.run(
        tmp_path, "hello", [], cancel_event=Event(), progress=events.append,
        workflow=classify_request("hello"),
    )

    assert result.message == "Hello from the agent"
    assert result.usage["totalTokens"] == 17
    assert any(event["type"] == "plan" for event in events)
    assert any(event["type"] == "text" for event in events)
    assert any(event["type"] == "usage" for event in events)
    assert any(event["type"] == "activity" for event in events)
