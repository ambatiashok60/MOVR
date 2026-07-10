from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.code_patch import PatchSet
from app.schemas.spec_placement import SpecPlacementDecision
from app.schemas.test_action_decision import TestActionDecision


class ExplorationRequest(BaseModel):
    """One evidence request. `reason` is mandatory reasoning: the model must say
    why it needs this file/search before we execute it."""

    kind: Literal["read_file", "search", "list_dir"]
    target: str
    reason: str = ""


class _Turn(BaseModel):
    reasoning: str = Field(
        default="",
        description="State what you know so far and why you are exploring or concluding.",
    )
    requests: list[ExplorationRequest] = Field(default_factory=list)


class SpecPlacementTurn(_Turn):
    output: SpecPlacementDecision | None = None


class TestActionTurn(_Turn):
    output: TestActionDecision | None = None


class PatchSetTurn(_Turn):
    output: PatchSet | None = None
