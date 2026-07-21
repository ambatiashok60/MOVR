from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.workspace import apply_hunks, diff_hunks, resolve_file, resolve_workspace


def test_workspace_must_be_inside_allowed_root(tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    config = SimpleNamespace(workspace_allowed_roots=[allowed])
    assert resolve_workspace(str(allowed), config) == allowed
    with pytest.raises(HTTPException) as error:
        resolve_workspace(str(tmp_path), config)
    assert error.value.status_code == 403


def test_workspace_child_accepted_sibling_rejected(tmp_path: Path):
    allowed = tmp_path / "allowed"
    child = allowed / "repo"
    sibling = tmp_path / "sibling"
    child.mkdir(parents=True)
    sibling.mkdir()
    config = SimpleNamespace(workspace_allowed_roots=[allowed])

    assert resolve_workspace(str(child), config) == child
    with pytest.raises(HTTPException) as error:
        resolve_workspace(str(sibling), config)
    assert error.value.status_code == 403


def test_missing_workspace_returns_400_not_403(tmp_path: Path):
    config = SimpleNamespace(workspace_allowed_roots=[tmp_path])
    with pytest.raises(HTTPException) as error:
        resolve_workspace(str(tmp_path / "does-not-exist"), config)
    assert error.value.status_code == 400
    assert "does not exist" in error.value.detail


def test_file_workspace_returns_400_not_403(tmp_path: Path):
    target = tmp_path / "file.txt"
    target.write_text("not a directory")
    config = SimpleNamespace(workspace_allowed_roots=[tmp_path])
    with pytest.raises(HTTPException) as error:
        resolve_workspace(str(target), config)
    assert error.value.status_code == 400
    assert "not a directory" in error.value.detail


def test_file_cannot_escape_workspace(tmp_path: Path):
    with pytest.raises(HTTPException):
        resolve_file(tmp_path, "../secret.txt")

def test_apply_selected_hunks_only():
    before = "one\ntwo\nthree\nfour\n"
    diff = "--- a/x.txt\n+++ b/x.txt\n@@ -1,2 +1,2 @@\n one\n-two\n+TWO\n@@ -3,2 +3,2 @@\n three\n-four\n+FOUR\n"
    hunks = diff_hunks(diff)
    assert len(hunks) == 2
    assert apply_hunks(before, diff, {hunks[0]["id"]}) == "one\nTWO\nthree\nfour\n"
