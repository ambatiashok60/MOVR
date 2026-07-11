from __future__ import annotations

from pydantic import BaseModel, Field


class DependencyMap(BaseModel):
    edges: dict[str, list[str]] = Field(default_factory=dict)

    def add(self, source: str, target: str) -> None:
        self.edges.setdefault(source, []).append(target)
