from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewFileChange(BaseModel):
    path: str
    operation: str
    test_target: str = ""
    summary: str = ""


class ApiReviewReport(BaseModel):
    """Everything a developer needs to review an API generation in minutes."""

    summary: str = ""
    files_changed: list[ReviewFileChange] = Field(default_factory=list)
    strategy: str = ""
    strategy_rationale: list[str] = Field(default_factory=list)
    mocks_planned: list[str] = Field(default_factory=list)
    examples_reused: list[str] = Field(default_factory=list)
    assertions_added: list[str] = Field(default_factory=list)
    validation_summary: str = ""
    remaining_risks: list[str] = Field(default_factory=list)
    markdown: str = ""
