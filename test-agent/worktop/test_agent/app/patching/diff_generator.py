from __future__ import annotations

import difflib


class DiffGenerator:
    def unified(self, before: str, after: str, path: str) -> str:
        return "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
