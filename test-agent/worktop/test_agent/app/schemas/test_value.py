from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TestValueVerdict = Literal[
    "NEW_COVERAGE",
    "MEANINGFUL_VARIATION",
    "PARTIAL_DUPLICATE",
    "FULL_DUPLICATE",
    "LOW_VALUE",
]


class TestValueAssessment(BaseModel):
    """Value verdict for one generated test against the existing inventory."""

    file_path: str
    test_title: str
    verdict: TestValueVerdict
    behavior_overlap: float = Field(ge=0.0, le=1.0, default=0.0)
    new_assertions: list[str] = Field(default_factory=list)
    duplicated_assertions: list[str] = Field(default_factory=list)
    new_navigations: list[str] = Field(default_factory=list)
    new_data_inputs: list[str] = Field(default_factory=list)
    closest_existing_test: str | None = None
    closest_existing_file: str | None = None
    rationale: str = ""


class TestValueReport(BaseModel):
    assessments: list[TestValueAssessment] = Field(default_factory=list)
    requires_approval: bool = False
    summary: str = ""
