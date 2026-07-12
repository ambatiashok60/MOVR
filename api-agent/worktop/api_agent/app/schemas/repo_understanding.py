from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DiscoveryRequest(BaseModel):
    """One tool request the discovery model wants executed."""

    kind: Literal["read_file", "search", "list_dir"]
    target: str = Field(
        description="Repo-relative path for read_file/list_dir, or a search term."
    )


class RepoUnderstanding(BaseModel):
    """Evidence-grounded repository understanding produced by the discovery loop.

    Nothing here is hardcoded per framework: the model reports what it actually
    found, for any language or test stack.
    """

    languages: list[str] = Field(default_factory=list)
    service_frameworks: list[str] = Field(default_factory=list)
    test_frameworks: list[str] = Field(default_factory=list)
    test_locations: list[str] = Field(default_factory=list)
    ci_test_command: str | None = None
    stage_test_command: str | None = None
    conventions: list[str] = Field(default_factory=list)
    example_test_paths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class DiscoveryTurn(BaseModel):
    """One turn of the discovery loop: either more requests, or a conclusion."""

    requests: list[DiscoveryRequest] = Field(default_factory=list)
    understanding: RepoUnderstanding | None = None
