from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ScenarioValueVerdict = Literal[
    "NEW_COVERAGE",
    "MEANINGFUL_VARIATION",
    "PARTIAL_DUPLICATE",
    "FULL_DUPLICATE",
    "LOW_VALUE",
]


class ScenarioValueAssessment(BaseModel):
    """Value verdict for one generated scenario."""

    api_scenario_id: str
    scenario_name: str
    verdict: ScenarioValueVerdict
    overlap: float = Field(ge=0.0, le=1.0, default=0.0)
    duplicate_of: str | None = None
    duplicate_source: Literal["existing_test", "generated_scenario"] | None = None
    rationale: str = ""


class ScenarioValueReport(BaseModel):
    assessments: list[ScenarioValueAssessment] = Field(default_factory=list)
    requires_approval: bool = False
    summary: str = ""
