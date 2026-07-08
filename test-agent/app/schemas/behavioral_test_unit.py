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


class PlaywrightDescribeBlock(BaseModel):
    file_path: str
    title: str
    start_line: int
    end_line: int
