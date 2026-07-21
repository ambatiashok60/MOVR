from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from worktop.api_agent.app.schemas.repo_understanding import DiscoveryRequest


class TestPlacementDecision(BaseModel):
    """Where one generated test file should land (test_agent spec-placement parity).

    ``extend_existing`` decisions carry the FULL merged content of the target
    file: every existing test must be preserved verbatim with the generated
    tests added following the file's conventions. The placement service
    deterministically verifies preservation and falls back to ``create_new``
    when the merge cannot be proven safe.
    """

    __test__ = False  # prevent pytest collection

    generated_path: str = Field(
        description="relative_path of the generated file this decision applies to"
    )
    action: Literal["create_new", "extend_existing"] = "create_new"
    target_existing_path: str | None = Field(
        default=None,
        description="Repo-relative path of the existing test file to extend",
    )
    merged_content: str | None = Field(
        default=None,
        description=(
            "Full content of the target existing file after adding the new "
            "tests; required for extend_existing"
        ),
    )
    rationale: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class TestPlacementOutput(BaseModel):
    __test__ = False

    decisions: list[TestPlacementDecision] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TestPlacementTurn(BaseModel):
    """One turn of agentic placement: gather repo evidence or conclude."""

    __test__ = False

    requests: list[DiscoveryRequest] = Field(default_factory=list)
    output: TestPlacementOutput | None = None
