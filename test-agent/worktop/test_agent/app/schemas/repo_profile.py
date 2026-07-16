from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RepoSupportStatus = Literal["supported", "supported_with_warnings", "unsupported"]


class RepoProfile(BaseModel):
    repo_path: str
    branch: str | None = None
    support_status: RepoSupportStatus = "unsupported"
    requires_bootstrap: bool = False
    support_reasons: list[str] = Field(default_factory=list)
    support_warnings: list[str] = Field(default_factory=list)
    support_blockers: list[str] = Field(default_factory=list)
    is_monorepo: bool = False
    monorepo_tooling: list[str] = Field(default_factory=list)
    app_roots: list[str] = Field(default_factory=list)
    playwright_configs: list[str] = Field(default_factory=list)
    playwright_spec_files: list[str] = Field(default_factory=list)
    package_manager: str | None = None
    package_scripts: dict[str, str] = Field(default_factory=dict)
    lockfiles: list[str] = Field(default_factory=list)
    detected_frameworks: list[str] = Field(default_factory=list)
    unsupported_signals: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
