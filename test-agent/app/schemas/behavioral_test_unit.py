from __future__ import annotations

from pydantic import BaseModel, Field


class BehavioralTestUnit(BaseModel):
    file_path: str
    describe_title: str | None = None
    test_title: str
    start_line: int
    end_line: int
    fixtures: list[str] = Field(default_factory=list)
    page_objects: list[str] = Field(default_factory=list)
    behavior_summary: str = ""
    source_excerpt: str = ""


class PlaywrightDescribeBlock(BaseModel):
    file_path: str
    title: str
    start_line: int
    end_line: int


class ExistingTestContext(BaseModel):
    file_path: str
    describe_title: str | None = None
    test_title: str
    start_line: int
    end_line: int
    fixtures: list[str] = Field(default_factory=list)
    page_objects: list[str] = Field(default_factory=list)
    behavior_summary: str = ""
    source_excerpt: str = ""


class AnchorFlowContext(BaseModel):
    """Reference-only proven flow used to seed an appended test.

    Unlike ExistingTestContext (an exact edit target for extend), this is a sibling
    test in the target spec whose setup/auth/navigation/fixtures/page objects the new
    appended test should reuse. It is never patched or replaced.
    """

    file_path: str
    describe_title: str | None = None
    anchor_test_title: str
    fixtures: list[str] = Field(default_factory=list)
    page_objects: list[str] = Field(default_factory=list)
    behavior_summary: str = ""
    source_excerpt: str = ""
    rationale: str = ""
