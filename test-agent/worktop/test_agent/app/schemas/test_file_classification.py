from __future__ import annotations

from pydantic import BaseModel


class TestFileClassification(BaseModel):
    path: str
    kind: str
    is_e2e_candidate: bool = False
    reason: str = ""
