from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.api_scenario import ApiScenario
from app.schemas.repo_understanding import DiscoveryRequest

StrategyConfidence = Literal["high", "medium", "low"]
TestTarget = Literal["ci", "stage"]


class ScenarioPlanOutput(BaseModel):
    scenarios: list[ApiScenario] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GeneratedTestFileOutput(BaseModel):
    relative_path: str
    content: str
    test_target: TestTarget
    summary: str


class TestCodeOutput(BaseModel):
    __test__ = False  # prevent pytest collection of this Pydantic model

    files: list[GeneratedTestFileOutput] = Field(default_factory=list)
    summary: str = "Generated API tests"
    strategy_name: str | None = None
    strategy_confidence: StrategyConfidence | None = None
    strategy_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ScenarioPlanTurn(BaseModel):
    """One turn of agentic scenario planning: gather evidence or conclude."""

    requests: list[DiscoveryRequest] = Field(default_factory=list)
    output: ScenarioPlanOutput | None = None


class TestCodeTurn(BaseModel):
    """One turn of agentic test code generation: gather evidence or conclude."""

    __test__ = False

    requests: list[DiscoveryRequest] = Field(default_factory=list)
    output: TestCodeOutput | None = None
