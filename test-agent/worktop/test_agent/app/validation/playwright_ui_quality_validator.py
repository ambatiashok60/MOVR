from __future__ import annotations

import re


from worktop.test_agent.app.schemas.code_patch import PatchSet
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.validation_result import ValidationCheck
from worktop.test_agent.utils.logging import get_logger

logger = get_logger(__name__)


class PlaywrightUiQualityValidator:
    SHALLOW_ASSERTIONS = (
        "toBeDefined(",
        "toBeTruthy(",
        "not.toBeNull(",
    )
    FLAKE_PATTERNS = (
        "waitForTimeout(",
        "setTimeout(",
        "networkidle",
    )

    def validate(
        self,
        patches: PatchSet | None,
        ui_context: PlaywrightUiContext | None = None,
    ) -> ValidationCheck:
        logger.info("[playwright-generation] stage=playwright_ui_quality status=started")
        if patches is None:
            return ValidationCheck(
                name="playwright_ui_quality",
                passed=True,
                output="No generated patches supplied for UI quality validation.",
            )

        findings: list[str] = []
        for patch in patches.patches:
            if not patch.path.endswith((".ts", ".tsx", ".js", ".jsx")):
                continue
            content = patch.content
            if not content.strip():
                findings.append(f"{patch.path}: generated patch has empty content")
                continue
            self._check_assertions(patch.path, content, findings)
            self._check_flake_patterns(patch.path, content, findings)
            self._check_locator_quality(patch.path, content, findings, ui_context)
            self._check_repo_patterns(patch.path, content, findings, ui_context)

        logger.info(
            "[playwright-generation] stage=playwright_ui_quality status=completed findings=%s",
            len(findings),
        )
        return ValidationCheck(
            name="playwright_ui_quality",
            passed=not findings,
            output="\n".join(findings) if findings else "Generated Playwright UI patches passed quality checks.",
        )

    def _check_assertions(self, path: str, content: str, findings: list[str]) -> None:
        if "test(" in content and "expect(" not in content:
            findings.append(f"{path}: Playwright test has no assertion")
        for assertion in self.SHALLOW_ASSERTIONS:
            if assertion in content:
                findings.append(f"{path}: shallow assertion `{assertion}` does not prove visible behavior")
        if "toBeVisible(" in content and not any(
            token in content
            for token in (
                "toHaveText(",
                "toContainText(",
                "toHaveURL(",
                "toHaveValue(",
                "toBeDisabled(",
                "toBeEnabled(",
                "toHaveCount(",
                "toHaveAttribute(",
            )
        ):
            findings.append(
                f"{path}: only visibility assertions found; add outcome assertions for changed UI state"
            )

    def _check_flake_patterns(self, path: str, content: str, findings: list[str]) -> None:
        for pattern in self.FLAKE_PATTERNS:
            if pattern in content:
                findings.append(f"{path}: flake-prone wait pattern `{pattern}` detected")

    def _check_locator_quality(
        self,
        path: str,
        content: str,
        findings: list[str],
        ui_context: PlaywrightUiContext | None,
    ) -> None:
        raw_locator_count = len(re.findall(r"\.locator\(\s*['\"](?:\.|#|\[|//)", content))
        if raw_locator_count:
            findings.append(
                f"{path}: raw CSS/XPath locator detected; prefer accessible locators or page objects"
            )
        if "getByTestId(" in content:
            existing_styles = {
                style
                for pattern in (ui_context.existing_spec_patterns if ui_context else [])
                for style in pattern.locator_styles
            }
            if "test_id" not in existing_styles and not any(
                element.locator_hint == "getByTestId"
                for element in (ui_context.ui_elements if ui_context else [])
            ):
                findings.append(
                    f"{path}: getByTestId used without detected repo/source test-id convention"
                )

    def _check_repo_patterns(
        self,
        path: str,
        content: str,
        findings: list[str],
        ui_context: PlaywrightUiContext | None,
    ) -> None:
        if ui_context is None:
            return
        has_mock_patterns = bool(ui_context.mock_patterns)
        touches_network_flow = any(token in content.lower() for token in ("api", "graphql", "route.fulfill", "page.route"))
        if has_mock_patterns and touches_network_flow and not any(
            token in content for token in ("page.route", "route.fulfill", "server.use", "mock", "stub")
        ):
            findings.append(
                f"{path}: network-dependent UI flow should reuse detected mock/stub patterns"
            )
        if ui_context.auth_session_patterns and "page.goto" in content and not any(
            token in content for token in ("storageState", "login", "test.use", "auth")
        ):
            findings.append(
                f"{path}: navigation flow should account for detected auth/session setup"
            )
