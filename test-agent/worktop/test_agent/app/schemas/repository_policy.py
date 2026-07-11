from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AssertionLocation = Literal["spec", "page_object", "any"]
LocatorOwner = Literal["page_object", "spec", "any"]


class GenerationPolicy(BaseModel):
    """Per-repository generation rules the engine must respect."""

    allow_before_each_updates: bool = True
    assertion_location: AssertionLocation = "any"
    locator_owner: LocatorOwner = "any"
    component_strategy: str = "component_objects"
    require_describe: bool = False
    rollback_failed_patch: bool = True
    allow_full_duplicates: bool = False


class RepositoryPolicy(BaseModel):
    """Repository-specific policy consulted before and during generation.

    Loaded from a policy file committed in the target repository; when no file
    exists, permissive defaults apply so behavior is unchanged for
    repositories that have not adopted policies.
    """

    source: str = "defaults"
    generation: GenerationPolicy = Field(default_factory=GenerationPolicy)
