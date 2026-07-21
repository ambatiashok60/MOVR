from pathlib import Path
from types import SimpleNamespace

from app.tools import ToolRunner, run_safe_command


def runner(root: Path) -> ToolRunner:
    return ToolRunner(root, SimpleNamespace(workspace_max_files=100, workspace_max_file_bytes=100_000))


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


def test_large_file_line_range_edit_stays_in_proposal(tmp_path: Path):
    source = tmp_path / "large.txt"
    source.write_text("".join(f"line {i}\n" for i in range(1, 2001)))
    tools = runner(tmp_path)
    result = tools.execute("replace_line_range", {
        "path": "large.txt", "start_line": 1000, "end_line": 1002, "new_text": "migrated A\nmigrated B\n",
    })

    assert result["range"] == [1000, 1002]
    assert source.read_text().splitlines()[999] == "line 1000"
    assert "migrated A" in tools.changes()[0].content

def test_dependency_graph_contains_imports_symbols_and_evidence(tmp_path: Path):
    (tmp_path / "api.py").write_text("from service import value\n@app.get('/items')\ndef items():\n    return value()\n")
    (tmp_path / "service.py").write_text("def value():\n    return 1\n")
    result = runner(tmp_path).execute("dependency_graph", {})
    graph = result["graph"]
    assert any(node["label"] == "value" for node in graph["nodes"])
    assert any(edge["kind"] == "import" for edge in graph["edges"])
    assert any(item["relation"] == "route:/items" for item in graph["evidence"])


def test_impact_analysis_connects_backend_route_to_frontend_consumer(tmp_path: Path):
    backend = tmp_path / "backend"
    frontend = tmp_path / "frontend"
    backend.mkdir(); frontend.mkdir()
    (backend / "api.py").write_text("@app.get('/api/scenarios')\ndef scenarios():\n    return []\n")
    (frontend / "scenario.service.ts").write_text(
        "export const load = () => http.get('/api/scenarios');\n"
    )

    result = runner(tmp_path).execute("impact_analysis", {"query": "scenarios"})
    affected = {item["path"] for item in result["affectedFiles"]}

    assert "backend/api.py" in affected
    assert "frontend/scenario.service.ts" in affected


def test_validate_overlay_reports_empty_content(tmp_path: Path):
    tools = runner(tmp_path)
    tools.execute("create_file", {"path": "empty.py", "content": ""})
    result = tools.execute("validate_overlay", {})
    assert result["valid"] is False
    assert "empty.py" in result["errors"][0]


def test_safe_command_disallows_shell_and_runs_allowlisted(tmp_path: Path):
    result = run_safe_command(tmp_path, ["python3", "-c", "print('ok')"], 5)
    assert result["returnCode"] == 0
    assert "ok" in result["stdout"]

    denied = tools_result = None
    try:
        run_safe_command(tmp_path, ["sh", "-c", "echo bad"], 5)
    except ValueError:
        denied = True
    assert denied is True
