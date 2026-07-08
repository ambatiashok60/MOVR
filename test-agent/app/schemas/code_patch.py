from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PatchOperation = Literal["create", "replace", "append"]


class CodePatch(BaseModel):
    path: str
    operation: PatchOperation
    start_line: int | None = None
    end_line: int | None = None
    content: str = ""
    reason: str = ""


class PatchSet(BaseModel):
    patches: list[CodePatch] = Field(default_factory=list)


class AppliedPatch(BaseModel):
    path: str
    operation: PatchOperation
    diff: str


class PatchWriteResult(BaseModel):
    applied: list[AppliedPatch] = Field(default_factory=list)
