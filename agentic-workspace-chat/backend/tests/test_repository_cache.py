from pathlib import Path

from app.repository_index import build_index


def test_incremental_index_reuses_unchanged_and_refreshes_changed_files(tmp_path: Path):
    root = tmp_path / "repo"
    cache = tmp_path / "cache"
    root.mkdir()
    source = root / "service.py"
    source.write_text("class Original:\n    pass\n")

    first = build_index(root, cache_dir=cache)
    second = build_index(root, cache_dir=cache)
    source.write_text("class Updated:\n    pass\n")
    third = build_index(root, cache_dir=cache)

    assert first["changed"] == 1
    assert second["reused"] == 1
    assert third["changed"] == 1
    assert any(node["label"] == "Updated" for node in third["nodes"])
