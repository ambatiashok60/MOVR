from __future__ import annotations

from pydantic import BaseModel, Field

from worktop.api_agent.app.schemas.autonomy import CapabilityAssessment
from worktop.api_agent.app.schemas.strategy_composition import TestGenerationPlan


class ApiEndpointCandidate(BaseModel):
    method: str
    path: str
    source_file: str
    service_name: str | None = None


class ExistingApiTestCandidate(BaseModel):
    path: str
    framework: str | None = None
    target: str | None = None
    strategy: str | None = None
    signals: list[str] = Field(default_factory=list)


class TeamTestStrategyProfile(BaseModel):
    primary_language: str | None = None
    languages: list[str] = Field(default_factory=list)
    service_frameworks: list[str] = Field(default_factory=list)
    build_tools: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    api_styles: list[str] = Field(default_factory=list)
    test_frameworks: list[str] = Field(default_factory=list)
    mocking_frameworks: list[str] = Field(default_factory=list)
    contract_tools: list[str] = Field(default_factory=list)
    auth_strategy: str | None = None
    api_test_locations: list[str] = Field(default_factory=list)
    stage_test_locations: list[str] = Field(default_factory=list)
    naming_conventions: list[str] = Field(default_factory=list)
    client_patterns: list[str] = Field(default_factory=list)
    auth_helpers: list[str] = Field(default_factory=list)
    base_test_classes: list[str] = Field(default_factory=list)
    fixture_files: list[str] = Field(default_factory=list)
    test_data_builders: list[str] = Field(default_factory=list)
    api_client_helpers: list[str] = Field(default_factory=list)
    existing_ci_test_examples: list[str] = Field(default_factory=list)
    existing_stage_test_examples: list[str] = Field(default_factory=list)
    endpoint_files: list[str] = Field(default_factory=list)
    openapi_files: list[str] = Field(default_factory=list)
    graphql_schema_files: list[str] = Field(default_factory=list)
    ci_command: str | None = None
    stage_command: str | None = None
    validation_commands: list[str] = Field(default_factory=list)
    confidence: str = "low"
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RepoProfile(BaseModel):
    repo_path: str
    package_manager: str | None = None
    build_tool: str | None = None
    languages: list[str] = Field(default_factory=list)
    service_frameworks: list[str] = Field(default_factory=list)
    api_styles: list[str] = Field(default_factory=list)
    test_frameworks: list[str] = Field(default_factory=list)
    mocking_frameworks: list[str] = Field(default_factory=list)
    contract_tools: list[str] = Field(default_factory=list)
    endpoints: list[ApiEndpointCandidate] = Field(default_factory=list)
    existing_tests: list[ExistingApiTestCandidate] = Field(default_factory=list)
    team_strategy: TeamTestStrategyProfile = Field(default_factory=TeamTestStrategyProfile)
    findings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    capability_assessment: CapabilityAssessment | None = None
    generation_plan: TestGenerationPlan | None = None
