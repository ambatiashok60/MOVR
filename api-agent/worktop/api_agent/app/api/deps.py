"""FastAPI dependencies that bridge to platform infrastructure.

``get_db`` lazily delegates to the platform's DB session dependency
(``worktop.config.db.get_db``). When that platform module is absent (standalone
deployments / tests) it yields ``None`` so route imports never fail; tests
override the dependency or monkeypatch downstream calls.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def get_db() -> Iterator[Any]:
    try:
        from worktop.config.db import get_db as _platform_get_db
    except Exception:
        yield None
        return

    generator = _platform_get_db()
    db = next(generator)
    try:
        yield db
    finally:
        try:
            next(generator)
        except StopIteration:
            pass
