from __future__ import annotations

from collections import Counter
from pathlib import Path

from worktop.core_services.app.utility.custom_logger.log_helpers import (
    log_exception,
    log_metric,
    log_step,
)
from worktop.core_services.app.utility.custom_logger.logging import (
    log_performance,
    logger,
)

from app.schemas.validation_result import ValidationCheck
from app.tools.playwright_parser_tool import PlaywrightParserTool


class PlaywrightValidator:
    def __init__(self) -> None:
        self.parser = PlaywrightParserTool()

    @log_performance("playwright_validator.validate")
    def validate(self, repo_path: str) -> ValidationCheck:
        log_step("playwright_validation_started", {"repo_path": repo_path})
        try:
            root = Path(repo_path)
            spec_files = self._find_spec_files(root)
            duplicate_messages: list[str] = []
            discovered_tests = 0

            for path in spec_files:
                relative_path = str(path.relative_to(root))
                content = path.read_text(encoding="utf-8", errors="ignore")
                tests = self.parser.extract_tests(relative_path, content)
                discovered_tests += len(tests)
                duplicate_messages.extend(self._duplicate_title_messages(relative_path, tests))

            log_metric("playwright_validation_spec_count", len(spec_files))
            log_metric("playwright_validation_test_count", discovered_tests)

            if not spec_files:
                return ValidationCheck(
                    name="playwright_discovery",
                    passed=False,
                    output="No TypeScript Playwright spec files discovered.",
                )
            if duplicate_messages:
                return ValidationCheck(
                    name="playwright_discovery",
                    passed=False,
                    output="\n".join(duplicate_messages),
                )

            logger.info("Playwright validation completed")
            return ValidationCheck(
                name="playwright_discovery",
                passed=True,
                output=f"Discovered {discovered_tests} Playwright test(s) in {len(spec_files)} spec file(s).",
            )
        except Exception as exc:
            log_exception(exc, context={"repo_path": repo_path, "stage": "playwright_validation"})
            raise

    def _find_spec_files(self, root: Path) -> list[Path]:
        spec_files: list[Path] = []
        for path in root.rglob("*.ts"):
            if not path.is_file() or self._is_ignored_path(path):
                continue
            if path.name.endswith((".spec.ts", ".e2e.ts")) and self._looks_like_playwright(path):
                spec_files.append(path)
        return spec_files

    def _looks_like_playwright(self, path: Path) -> bool:
        content = path.read_text(encoding="utf-8", errors="ignore")
        path_parts = {part.lower() for part in path.parts}
        return (
            "@playwright/test" in content
            or "playwright" in content.lower()
            or (
                bool(path_parts.intersection({"e2e", "playwright"}))
                and "test(" in content
            )
        )

    def _duplicate_title_messages(self, relative_path: str, tests) -> list[str]:
        titles = [
            f"{test.describe_title or '<root>'} :: {test.test_title}"
            for test in tests
        ]
        counts = Counter(titles)
        return [
            f"Duplicate Playwright test title in {relative_path}: {title}"
            for title, count in counts.items()
            if count > 1
        ]

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
