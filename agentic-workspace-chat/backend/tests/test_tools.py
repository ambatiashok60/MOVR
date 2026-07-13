from pathlib import Path
from types import SimpleNamespace

from app.tools import ToolRunner


def runner(root: Path) -> ToolRunner:
    return ToolRunner(root, SimpleNamespace(workspace_max_files=100, workspace_max_file_bytes=10_000))


def test_replacement_stays_in_proposal(tmp_path: Path):
    source = tmp_path / "service.py"
    source.write_text("def value():\n    return 1\n")
    tools = runner(tmp_path)

    result = tools.execute("replace_in_file", {
        "path": "service.py", "old_text": "return 1", "new_text": "return 2",
    })

    assert result["operation"] == "update"
    assert source.read_text().endswith("return 1\n")
    assert tools.changes()[0].content.endswith("return 2\n")


def test_new_file_is_proposed_without_writing(tmp_path: Path):
    tools = runner(tmp_path)
    tools.execute("create_file", {"path": "feature/model.ts", "content": "export interface Model {}\n"})

    assert not (tmp_path / "feature/model.ts").exists()
    assert tools.changes()[0].operation == "create"
