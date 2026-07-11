from __future__ import annotations

from pydantic import BaseModel, Field


class UiRouteEvidence(BaseModel):
    path: str
    file_path: str
    line: int | None = None
    reason: str = ""


class UiElementEvidence(BaseModel):
    file_path: str
    line: int | None = None
    text: str = ""
    role: str | None = None
    locator_hint: str = ""
    reason: str = ""


class MockPatternEvidence(BaseModel):
    kind: str
    file_path: str
    line: int | None = None
    endpoint_or_handler: str = ""
    helper_name: str | None = None
    reason: str = ""


class AuthSessionEvidence(BaseModel):
    kind: str
    file_path: str
    line: int | None = None
    evidence: str = ""
    reason: str = ""


class TestDataEvidence(BaseModel):
    kind: str
    file_path: str
    line: int | None = None
    symbol: str = ""
    reason: str = ""


class ExistingSpecPattern(BaseModel):
    file_path: str
    locator_styles: list[str] = Field(default_factory=list)
    assertion_styles: list[str] = Field(default_factory=list)
    uses_page_route: bool = False
    uses_msw: bool = False
    uses_storage_state: bool = False
    uses_page_objects: bool = False
    tags: list[str] = Field(default_factory=list)
    setup_hooks: list[str] = Field(default_factory=list)


class CiCommandEvidence(BaseModel):
    command: str
    reason: str = ""


class QualityRequirement(BaseModel):
    rule: str
    severity: str = "warning"
    reason: str = ""


class PlaywrightUiContext(BaseModel):
    routes: list[UiRouteEvidence] = Field(default_factory=list)
    ui_elements: list[UiElementEvidence] = Field(default_factory=list)
    mock_patterns: list[MockPatternEvidence] = Field(default_factory=list)
    auth_session_patterns: list[AuthSessionEvidence] = Field(default_factory=list)
    test_data_patterns: list[TestDataEvidence] = Field(default_factory=list)
    existing_spec_patterns: list[ExistingSpecPattern] = Field(default_factory=list)
    ci_commands: list[CiCommandEvidence] = Field(default_factory=list)
    page_objects: list[str] = Field(default_factory=list)
    fixtures: list[str] = Field(default_factory=list)
    helpers: list[str] = Field(default_factory=list)
    quality_requirements: list[QualityRequirement] = Field(default_factory=list)
