from __future__ import annotations

from pathlib import Path
from typing import Any

from worktop.core_services.app.utility.custom_logger.log_helpers import (
    log_card_simple,
    log_exception,
    log_metric,
    log_step,
)
from worktop.core_services.app.utility.custom_logger.logging import (
    log_performance,
    logger,
)

from app.schemas.test_file_classification import TestFileClassification


class TestFileClassifierService:
    SPEC_SUFFIXES = (
        ".spec.ts",
        ".spec.tsx",
        ".e2e.ts",
        ".e2e.tsx",
        ".test.ts",
        ".test.tsx",
        ".pw.ts",
        ".pw.tsx",
        ".playwright.ts",
        ".playwright.tsx",
    )

    @log_performance("test_file_classifier_service.classify")
    def classify(self, repo_path: str) -> list[TestFileClassification]:
        log_step("test_file_classification_started", {"repo_path": repo_path})
        try:
            root = Path(repo_path)
            files = []
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
                    continue
                if self._is_ignored_path(path):
                    continue
                kind, is_e2e_candidate, reason = self._classify_file(path)
                files.append(
                    TestFileClassification(
                        path=str(path.relative_to(root)),
                        kind=kind,
                        is_e2e_candidate=is_e2e_candidate,
                        reason=reason,
                    )
                )
            log_metric("classified_test_files_count", len(files))
            logger.info("Test file classification completed")
            return files
        except Exception as exc:
            log_exception(exc, context={"repo_path": repo_path, "stage": "test_file_classification"})
            raise

    def _classify_file(self, path: Path) -> tuple[str, bool, str]:
        if not path.name.endswith(self.SPEC_SUFFIXES):
            return "source", False, "Not a spec filename"
        content = path.read_text(encoding="utf-8", errors="ignore")
        lower_content = content.lower()
        path_parts = {part.lower() for part in path.parts}
        if "@playwright/test" in content or "playwright" in lower_content:
            return "e2e", True, "Playwright import or keyword detected"
        if bool(path_parts.intersection({"e2e", "playwright"})) and "test(" in lower_content:
            return "e2e", True, "E2E path and Playwright-like test blocks detected"
        return "unit_or_integration", False, "Spec file does not look like Playwright E2E"

    def _is_ignored_path(self, path: Path) -> bool:
        ignored_parts = {
            ".git",
            "node_modules",
            "dist",
            "build",
            "coverage",
            ".next",
            ".turbo",
            ".nx",
        }
        return bool(set(path.parts).intersection(ignored_parts))
