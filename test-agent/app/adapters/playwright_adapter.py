from __future__ import annotations

from typing import Any

from app.adapters.technology_adapter import TechnologyAdapter
from app.patching.scoped_patch_writer import ScopedPatchWriter
from app.schemas.behavioral_test_unit import BehavioralTestUnit
from app.schemas.code_patch import PatchSet, PatchWriteResult
from app.schemas.repo_profile import RepoProfile
from app.schemas.repository_inventory import RepositoryInventory
from app.schemas.test_file_classification import TestFileClassification
from app.schemas.validation_result import ValidationResult
from app.services.behavioral_inventory_service import BehavioralInventoryService
from app.services.inventory_service import InventoryService
from app.services.repo_strategy_service import RepoStrategyService
from app.services.test_file_classifier_service import TestFileClassifierService
from app.validation.repo_command_validator import RepoCommandValidator


class PlaywrightAdapter(TechnologyAdapter):
    """Playwright/TypeScript implementation of the technology boundary."""

    technology = "playwright"

    def __init__(self) -> None:
        self.repo_strategy = RepoStrategyService()
        self.classifier = TestFileClassifierService()
        self.inventory = InventoryService()
        self.behavioral_inventory = BehavioralInventoryService()
        self.patch_writer = ScopedPatchWriter()
        self.validator = RepoCommandValidator()

    def analyze_repository(self, repo_path: str, branch: str | None = None) -> RepoProfile:
        return self.repo_strategy.detect(repo_path, branch)

    def classify_test_files(self, repo_path: str) -> list[TestFileClassification]:
        return self.classifier.classify(repo_path)

    def build_inventory(
        self,
        repo_path: str,
        classifications: list[TestFileClassification],
    ) -> RepositoryInventory:
        return self.inventory.build(repo_path, classifications)

    def build_flow_inventory(
        self, inventory: RepositoryInventory
    ) -> list[BehavioralTestUnit]:
        return self.behavioral_inventory.extract(inventory)

    def apply_patch(self, repo_path: str, patches: PatchSet) -> PatchWriteResult:
        return self.patch_writer.apply(repo_path, patches)

    def rollback(self, repo_path: str, result: PatchWriteResult) -> None:
        self.patch_writer.rollback(repo_path, result)

    def validate(
        self,
        repo_path: str,
        patches: PatchSet,
        context: Any | None = None,
    ) -> ValidationResult:
        return self.validator.validate(repo_path, patches, context)
