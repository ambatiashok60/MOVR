from __future__ import annotations

from pydantic import BaseModel, Field


class SourceSnippet(BaseModel):
    path: str
    reason: str
    content: str


class ExistingTestExample(BaseModel):
    path: str
    target: str | None = None
    framework: str | None = None
    strategy: str | None = None
    relevance_score: int = 0
    signals: list[str] = Field(default_factory=list)
    content: str


class DependencyCandidate(BaseModel):
    name: str
    type_name: str | None = None
    source_file: str
    dependency_kind: str = "unknown"
    reason: str


class GenerationSourceContext(BaseModel):
    endpoint_sources: list[SourceSnippet] = Field(default_factory=list)
    existing_test_examples: list[ExistingTestExample] = Field(default_factory=list)
    dependency_candidates: list[DependencyCandidate] = Field(default_factory=list)
    fixture_snippets: list[SourceSnippet] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
