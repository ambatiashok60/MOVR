from __future__ import annotations

from pydantic import BaseModel


class GeneratedFile(BaseModel):
    path: str
    operation: str = "created"
    test_target: str
    summary: str
