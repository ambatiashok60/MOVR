from __future__ import annotations

from pydantic import BaseModel, Field


class BehaviorCoverageEntry(BaseModel):
    """Behavioral coverage captured for one test block.

    Coverage is tracked at the business-behavior level rather than line level:
    the assertions, navigations, API touchpoints, and reusable flow artifacts a
    test exercises are the signals that must survive generation.
    """

    file_path: str
    describe_title: str | None = None
    test_title: str
    assertions: list[str] = Field(default_factory=list)
    navigations: list[str] = Field(default_factory=list)
    api_calls: list[str] = Field(default_factory=list)
    interactions: list[str] = Field(default_factory=list)
    data_inputs: list[str] = Field(default_factory=list)
    page_objects: list[str] = Field(default_factory=list)
    fixtures: list[str] = Field(default_factory=list)

    @property
    def coverage_key(self) -> tuple[str, str]:
        return (self.file_path, self.test_title)

    def signals(self) -> set[str]:
        return {
            *(f"assert:{item}" for item in self.assertions),
            *(f"nav:{item}" for item in self.navigations),
            *(f"api:{item}" for item in self.api_calls),
            *(f"interact:{item}" for item in self.interactions),
            *(f"data:{item}" for item in self.data_inputs),
        }


class CoverageModification(BaseModel):
    """A behavior that survived generation but with a changed signal set."""

    file_path: str
    test_title: str
    lost_signals: list[str] = Field(default_factory=list)
    gained_signals: list[str] = Field(default_factory=list)


class CoveragePreservationReport(BaseModel):
    """Diff between the behavioral coverage graph before and after generation."""

    preserved: list[BehaviorCoverageEntry] = Field(default_factory=list)
    added: list[BehaviorCoverageEntry] = Field(default_factory=list)
    removed: list[BehaviorCoverageEntry] = Field(default_factory=list)
    modified: list[CoverageModification] = Field(default_factory=list)
    coverage_preserved: bool = True
    summary: list[str] = Field(default_factory=list)
