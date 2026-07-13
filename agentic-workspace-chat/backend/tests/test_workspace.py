from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.workspace import resolve_file, resolve_workspace


def test_workspace_must_be_inside_allowed_root(tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    config = SimpleNamespace(workspace_allowed_roots=[allowed])
    assert resolve_workspace(str(allowed), config) == allowed
    with pytest.raises(HTTPException) as error:
        resolve_workspace(str(tmp_path), config)
    assert error.value.status_code == 403


def test_file_cannot_escape_workspace(tmp_path: Path):
    with pytest.raises(HTTPException):
        resolve_file(tmp_path, "../secret.txt")

