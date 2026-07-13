from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PatchOperation = Literal[
    "create", "replace", "append", "insert_class_member",
    "insert_object_property", "insert_import",
]


class CodePatch(BaseModel):
    path: str
    operation: PatchOperation
    start_line: int | None = None
    end_line: int | None = None
    content: str = ""
    reason: str = ""
    target_symbol: str | None = None
    member_name: str | None = None


class PatchSet(BaseModel):
    patches: list[CodePatch] = Field(default_factory=list)


class AppliedPatch(BaseModel):
    path: str
    operation: PatchOperation
    diff: str
    backup_path: str | None = None
    original_content: str | None = None


class PatchWriteResult(BaseModel):
    applied: list[AppliedPatch] = Field(default_factory=list)
