from __future__ import annotations

from pathlib import Path


from worktop.test_agent.app.schemas.test_file_classification import TestFileClassification
from worktop.core_services.app.utility.custom_logger.logging import logger



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

    def classify(self, repo_path: str) -> list[TestFileClassification]:
        logger.info(
            "[playwright-generation] stage=test_file_classification status=started repo=%s",
            repo_path,
        )
        try:
            root = Path(repo_path)
            files = []
            scanned = 0
            ignored = 0
            typed = 0
            for path in root.rglob("*"):
                scanned += 1
                if not path.is_file():
                    continue
                if self._is_ignored_path(path):
                    ignored += 1
                    logger.debug(
                        "[playwright-generation] stage=test_file_classification "
                        "status=skipped_ignored path=%s",
                        path,
                    )
                    continue
                if path.suffix not in {".ts", ".tsx"}:
                    continue
                typed += 1
                kind, is_e2e_candidate, reason = self._classify_file(path)
                logger.debug(
                    "[playwright-generation] stage=test_file_classification "
                    "status=classified path=%s kind=%s e2e_candidate=%s reason=%s",
                    path.relative_to(root),
                    kind,
                    is_e2e_candidate,
                    reason,
                )
                files.append(
                    TestFileClassification(
                        path=str(path.relative_to(root)),
                        kind=kind,
                        is_e2e_candidate=is_e2e_candidate,
                        reason=reason,
                    )
                )
            logger.info(
                "[playwright-generation] stage=test_file_classification status=completed "
                "scanned=%s ignored=%s ts_files=%s classified=%s e2e_candidates=%s",
                scanned,
                ignored,
                typed,
                len(files),
                sum(1 for item in files if item.is_e2e_candidate),
            )
            return files
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=test_file_classification status=failed repo=%s error=%s",
                repo_path,
                exc,
            )
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
