from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.api_scenario import ApiScenario


class ScenarioPlanOutput(BaseModel):
    scenarios: list[ApiScenario] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GeneratedTestFileOutput(BaseModel):
    relative_path: str
    content: str
    test_target: str
    summary: str


class TestCodeOutput(BaseModel):
    files: list[GeneratedTestFileOutput] = Field(default_factory=list)
    summary: str = "Generated API tests"
    strategy_name: str | None = None
    strategy_confidence: str | None = None
    strategy_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
