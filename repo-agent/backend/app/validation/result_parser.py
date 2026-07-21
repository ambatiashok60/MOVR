"""Normalize a command outcome into a status string."""

from __future__ import annotations


def status_from_exit(exit_code: int | None) -> str:
    if exit_code is None:
        return "skipped"
    return "passed" if exit_code == 0 else "failed"
