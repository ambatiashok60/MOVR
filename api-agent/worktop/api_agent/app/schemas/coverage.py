from __future__ import annotations

from pydantic import BaseModel, Field


class ApiCoverageEntry(BaseModel):
    """API behavioral coverage carried by one test file.

    Tracks business-level API coverage — endpoints exercised, status codes and
    schema shapes asserted, auth signals — rather than line coverage.
    """

    file_path: str
    endpoints: list[str] = Field(default_factory=list)
    status_assertions: list[str] = Field(default_factory=list)
    body_assertions: list[str] = Field(default_factory=list)
    auth_signals: list[str] = Field(default_factory=list)

    def signals(self) -> set[str]:
        return {
            *(f"endpoint:{item}" for item in self.endpoints),
            *(f"status:{item}" for item in self.status_assertions),
            *(f"body:{item}" for item in self.body_assertions),
            *(f"auth:{item}" for item in self.auth_signals),
        }


class ApiCoverageModification(BaseModel):
    file_path: str
    lost_signals: list[str] = Field(default_factory=list)
    gained_signals: list[str] = Field(default_factory=list)


class ApiCoverageReport(BaseModel):
    """Diff of API coverage before and after generated files were written."""

    preserved: list[ApiCoverageEntry] = Field(default_factory=list)
    added: list[ApiCoverageEntry] = Field(default_factory=list)
    removed: list[ApiCoverageEntry] = Field(default_factory=list)
    modified: list[ApiCoverageModification] = Field(default_factory=list)
    coverage_preserved: bool = True
    summary: list[str] = Field(default_factory=list)
