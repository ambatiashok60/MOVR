from __future__ import annotations

from pydantic import BaseModel, Field


class ApiGenerationPolicy(BaseModel):
    """Per-repository API test generation rules the engine must respect."""

    forbid_real_network_in_ci: bool = True
    require_mocks_for_ci: bool = False
    allowed_test_frameworks: list[str] = Field(default_factory=list)
    require_negative_scenarios: bool = False
    allow_full_duplicates: bool = False
    max_files_per_generation: int = 10


class RepositoryPolicy(BaseModel):
    """Repository-specific policy consulted before and during generation.

    Loaded from a policy file committed in the target repository; when no file
    exists, permissive defaults apply so behavior is unchanged for
    repositories that have not adopted policies.
    """

    source: str = "defaults"
    generation: ApiGenerationPolicy = Field(default_factory=ApiGenerationPolicy)
