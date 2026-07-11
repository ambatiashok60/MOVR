from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewFileChange(BaseModel):
    path: str
    operation: str
    reason: str = ""


class ReviewReport(BaseModel):
    """Everything a developer needs to review the generation in minutes.

    A raw diff forces the reviewer to reconstruct the reasoning; this report
    states what changed, what was reused, why the action was chosen, and what
    risks remain — with a rendered markdown version for humans.
    """

    summary: str = ""
    files_changed: list[ReviewFileChange] = Field(default_factory=list)
    flows_reused: list[str] = Field(default_factory=list)
    flows_added: list[str] = Field(default_factory=list)
    action: str = ""
    action_rationale: str = ""
    placement_rationale: str = ""
    methods_reused: list[str] = Field(default_factory=list)
    methods_created: list[str] = Field(default_factory=list)
    locators_reused: list[str] = Field(default_factory=list)
    assertions_added: list[str] = Field(default_factory=list)
    validation_summary: str = ""
    remaining_risks: list[str] = Field(default_factory=list)
    markdown: str = ""
