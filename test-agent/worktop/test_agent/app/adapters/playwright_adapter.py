from __future__ import annotations

from typing import Any

from worktop.test_agent.app.adapters.technology_adapter import TechnologyAdapter
from worktop.test_agent.app.patching.scoped_patch_writer import ScopedPatchWriter
from worktop.test_agent.app.schemas.behavioral_test_unit import BehavioralTestUnit
from worktop.test_agent.app.schemas.code_patch import PatchSet, PatchWriteResult
from worktop.test_agent.app.schemas.repo_profile import RepoProfile
from worktop.test_agent.app.schemas.repository_inventory import RepositoryInventory
from worktop.test_agent.app.schemas.test_file_classification import TestFileClassification
from worktop.test_agent.app.schemas.validation_result import ValidationResult
from worktop.test_agent.app.services.behavioral_inventory_service import BehavioralInventoryService
from worktop.test_agent.app.services.inventory_service import InventoryService
from worktop.test_agent.app.services.repo_strategy_service import RepoStrategyService
from worktop.test_agent.app.services.test_file_classifier_service import TestFileClassifierService
from worktop.test_agent.app.validation.repo_command_validator import RepoCommandValidator


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
