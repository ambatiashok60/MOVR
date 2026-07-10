from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.behavioral_test_unit import BehavioralTestUnit
from app.schemas.code_patch import PatchSet, PatchWriteResult
from app.schemas.repo_profile import RepoProfile
from app.schemas.repository_inventory import RepositoryInventory
from app.schemas.test_file_classification import TestFileClassification
from app.schemas.validation_result import ValidationResult


class TechnologyAdapter(ABC):
    """Boundary between the core generation intelligence and one technology.

    Flow reasoning, decisions, patch planning, validation loops, repair,
    coverage, and reporting are technology-agnostic; everything that knows how
    a specific stack looks on disk — how to analyze the repository, inventory
    its flows, apply patches, and validate — lives behind this interface.
    Adding REST Assured, GraphQL, or gRPC support means writing an adapter,
    not duplicating the orchestration.
    """

    technology: str = "unknown"

    @abstractmethod
    def analyze_repository(self, repo_path: str, branch: str | None = None) -> RepoProfile:
        """Detect support status, framework signals, and validation commands."""

    @abstractmethod
    def classify_test_files(self, repo_path: str) -> list[TestFileClassification]:
        """Classify the repository's test files for this technology."""

    @abstractmethod
    def build_inventory(
        self,
        repo_path: str,
        classifications: list[TestFileClassification],
    ) -> RepositoryInventory:
        """Build the repository inventory (files, hashes, reusable artifacts)."""

    @abstractmethod
    def build_flow_inventory(
        self, inventory: RepositoryInventory
    ) -> list[BehavioralTestUnit]:
        """Extract the behavioral flow units existing tests already prove."""

    @abstractmethod
    def apply_patch(self, repo_path: str, patches: PatchSet) -> PatchWriteResult:
        """Apply a patch set to the repository."""

    @abstractmethod
    def rollback(self, repo_path: str, result: PatchWriteResult) -> None:
        """Undo a previously applied patch set."""

    @abstractmethod
    def validate(
        self,
        repo_path: str,
        patches: PatchSet,
        context: Any | None = None,
    ) -> ValidationResult:
        """Run this technology's validation over the applied patches."""
