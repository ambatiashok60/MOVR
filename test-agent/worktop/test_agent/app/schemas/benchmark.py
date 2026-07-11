from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ScenarioKind = Literal[
    "append",
    "extend",
    "create_spec",
    "partial_flow",
    "locator_creation",
    "method_reuse",
    "patch_repair",
    "replacement",
    "hook_update",
    "naming",
]


class BenchmarkExpectation(BaseModel):
    """Golden truth for one scenario."""

    action: str | None = None
    target_spec: str | None = None
    reuse_signals: list[str] = Field(default_factory=list)
    validation_should_pass: bool = True
    max_latency_ms: float | None = None


class BenchmarkScenario(BaseModel):
    name: str
    kind: ScenarioKind
    repo_path: str = ""
    test_case_name: str = ""
    steps: list[str] = Field(default_factory=list)
    expected: BenchmarkExpectation = Field(default_factory=BenchmarkExpectation)


class ScenarioOutcome(BaseModel):
    scenario: str
    kind: ScenarioKind
    passed: bool = False
    decision_correct: bool | None = None
    placement_correct: bool | None = None
    reuse_ok: bool | None = None
    validation_passed: bool | None = None
    patch_applied: bool = False
    repair_attempted: bool = False
    latency_ms: float = 0.0
    error: str = ""
    failures: list[str] = Field(default_factory=list)


class BenchmarkReport(BaseModel):
    outcomes: list[ScenarioOutcome] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class BenchmarkRegression(BaseModel):
    metric: str
    baseline: float
    current: float
    delta: float
