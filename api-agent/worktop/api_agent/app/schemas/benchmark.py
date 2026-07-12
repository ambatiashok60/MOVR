from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BenchmarkKind = Literal["scenario_plan", "code_generation"]


class BenchmarkExpectation(BaseModel):
    """Golden truth for one benchmark case."""

    min_scenarios: int = 0
    expected_scenario_types: list[str] = Field(default_factory=list)
    expected_strategy: str | None = None
    expect_generated_files: bool = True
    validation_should_pass: bool = True
    max_latency_ms: float | None = None


class BenchmarkCase(BaseModel):
    name: str
    kind: BenchmarkKind
    repo_path: str = ""
    story_title: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    scenario_name: str = ""
    scenario_steps: list[str] = Field(default_factory=list)
    assertions: list[str] = Field(default_factory=list)
    expected: BenchmarkExpectation = Field(default_factory=BenchmarkExpectation)


class CaseOutcome(BaseModel):
    case: str
    kind: BenchmarkKind
    passed: bool = False
    latency_ms: float = 0.0
    error: str = ""
    failures: list[str] = Field(default_factory=list)


class BenchmarkReport(BaseModel):
    outcomes: list[CaseOutcome] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class BenchmarkRegression(BaseModel):
    metric: str
    baseline: float
    current: float
    delta: float
