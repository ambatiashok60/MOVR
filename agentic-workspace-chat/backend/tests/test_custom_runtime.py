from pathlib import Path

import pytest

from app.custom_runtime import CustomToolStore, execute_code, validate_code


def test_constrained_tool_transforms_in_memory():
    code = "def transform(files, args):\n    return {path: text.replace(args['old'], args['new']) for path, text in files.items()}\n"
    result = execute_code(code, {"a.py": "old value"}, {"old": "old", "new": "new"})
    assert result == {"a.py": "new value"}


def test_constrained_tool_rejects_import_and_open():
    with pytest.raises(ValueError):
        validate_code("import os\ndef transform(files, args):\n    return files\n")
    with pytest.raises(ValueError):
        validate_code("def transform(files, args):\n    return open('/tmp/x').read()\n")


def test_persistent_tool_is_written_to_state_directory(tmp_path: Path):
    config = type("Config", (), {"agent_state_dir": tmp_path})()
    store = CustomToolStore(config)
    proposal = store.proposal(
        "rename-token", "Rename a token", "def transform(files, args):\n    return files\n", [], {}, True,
    )
    store.install(proposal)
    assert store.installed()[0]["manifest"]["name"] == "rename-token"

