from __future__ import annotations

from collections import Counter
from pathlib import Path


from worktop.test_agent.app.schemas.validation_result import ValidationCheck
from worktop.test_agent.app.schemas.code_patch import PatchSet
from worktop.test_agent.app.tools.playwright_parser_tool import PlaywrightParserTool
from worktop.core_services.app.utility.custom_logger.logging import logger



class PlaywrightValidator:
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

    def __init__(self) -> None:
        self.parser = PlaywrightParserTool()

    def validate(self, repo_path: str, patches: PatchSet | None = None) -> ValidationCheck:
        logger.info(
            "[playwright-generation] stage=playwright_validation status=started repo=%s",
            repo_path,
        )
        try:
            root = Path(repo_path)
            if patches is None or len(patches.patches) != 1:
                return ValidationCheck(
                    name="playwright_structure",
                    passed=False,
                    output="Validation requires exactly one generated patch.",
                )

            relative_path = patches.patches[0].path
            path = (root / relative_path).resolve()
            if root.resolve() != path and root.resolve() not in path.parents:
                return ValidationCheck(
                    name="playwright_structure",
                    passed=False,
                    output=f"Patch path escapes repository root: {relative_path}",
                )
            if not path.is_file():
                return ValidationCheck(
                    name="playwright_structure",
                    passed=False,
                    output=f"Patched file does not exist: {relative_path}",
                )

            content = path.read_text(encoding="utf-8", errors="ignore")
            tests = self.parser.extract_tests(relative_path, content)
            duplicate_messages = self._duplicate_title_messages(relative_path, tests)
            discovered_tests = len(tests)

            logger.info(
                "[playwright-generation] stage=playwright_validation discovered_specs=%s discovered_tests=%s",
                1,
                discovered_tests,
            )

            if not tests:
                return ValidationCheck(
                    name="playwright_structure",
                    passed=False,
                    output=f"No Playwright tests discovered in patched file: {relative_path}",
                )
            if duplicate_messages:
                return ValidationCheck(
                    name="playwright_structure",
                    passed=False,
                    output="\n".join(duplicate_messages),
                )

            logger.info("[playwright-generation] stage=playwright_validation status=completed")
            return ValidationCheck(
                name="playwright_structure",
                passed=True,
                output=f"Discovered {discovered_tests} Playwright test(s) in patched file {relative_path}.",
            )
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=playwright_validation status=failed repo=%s error=%s",
                repo_path,
                exc,
            )
            raise

    def _find_spec_files(self, root: Path) -> list[Path]:
        spec_files: list[Path] = []
        for path in root.rglob("*"):
            if not path.is_file() or self._is_ignored_path(path):
                continue
            if path.name.endswith(self.SPEC_SUFFIXES) and self._looks_like_playwright(path):
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
        titles = [test.test_title for test in tests]
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
