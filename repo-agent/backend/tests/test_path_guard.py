"""PathGuard is the workspace sandbox — its escapes must be airtight."""

from __future__ import annotations

import pytest

from app.workspace.path_guard import PathGuard


def test_allows_nested_relative_path(workspace):
    guard = PathGuard()
    resolved = guard.resolve_inside_workspace(workspace, "sub/dir/file.py")
    assert str(resolved).startswith(str(workspace.resolve()))


def test_rejects_parent_traversal(workspace):
    guard = PathGuard()
    with pytest.raises(PermissionError):
        guard.resolve_inside_workspace(workspace, "../../.aws/config")


def test_rejects_absolute_outside(workspace):
    guard = PathGuard()
    with pytest.raises(PermissionError):
        guard.resolve_inside_workspace(workspace, "/etc/passwd")


def test_allows_dot(workspace):
    guard = PathGuard()
    resolved = guard.resolve_inside_workspace(workspace, ".")
    assert resolved == workspace.resolve()
