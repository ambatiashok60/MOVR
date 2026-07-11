from __future__ import annotations

from pydantic import BaseModel, Field

from worktop.test_agent.app.schemas.test_file_classification import TestFileClassification


class RepositoryInventory(BaseModel):
    repo_path: str = ""
    repo_head: str | None = None
    file_hashes: dict[str, str] = Field(default_factory=dict)
    test_files: list[TestFileClassification] = Field(default_factory=list)
    page_objects: list[str] = Field(default_factory=list)
    fixtures: list[str] = Field(default_factory=list)
    helpers: list[str] = Field(default_factory=list)
