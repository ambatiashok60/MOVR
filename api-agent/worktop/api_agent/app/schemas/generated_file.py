from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class GeneratedFile(BaseModel):
    path: str
    operation: Literal["created", "updated"] = "created"
    test_target: str
    summary: str
