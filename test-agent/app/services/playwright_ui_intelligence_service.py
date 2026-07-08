from __future__ import annotations

import re
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

from app.schemas.playwright_ui_context import (
    AuthSessionEvidence,
    CiCommandEvidence,
    ExistingSpecPattern,
    MockPatternEvidence,
    PlaywrightUiContext,
    QualityRequirement,
    TestDataEvidence,
    UiElementEvidence,
    UiRouteEvidence,
)
from app.schemas.repo_profile import RepoProfile
from app.schemas.repository_inventory import RepositoryInventory


class PlaywrightUiIntelligenceService:
    MAX_FILE_BYTES = 240_000
    MAX_EVIDENCE_PER_KIND = 80

    ROUTE_PATTERNS = (
        re.compile(r"\bpath\s*:\s*['\"](?P<path>[^'\"]+)['\"]"),
        re.compile(r"<Route[^>]*\bpath\s*=\s*['\"](?P<path>[^'\"]+)['\"]"),
        re.compile(r"\bcreateFileRoute\s*\(\s*['\"](?P<path>[^'\"]+)['\"]"),
    )
    TEST_ID_PATTERN = re.compile(r"\bdata-testid\s*=\s*['\"](?P<value>[^'\"]+)['\"]")
    ARIA_LABEL_PATTERN = re.compile(r"\baria-label\s*=\s*['\"](?P<value>[^'\"]+)['\"]")
    ROLE_PATTERN = re.compile(r"\brole\s*=\s*['\"](?P<value>[^'\"]+)['\"]")
    PLACEHOLDER_PATTERN = re.compile(r"\bplaceholder\s*=\s*['\"](?P<value>[^'\"]+)['\"]")
    BUTTON_TEXT_PATTERN = re.compile(r"<button[^>]*>(?P<value>[^<{]{2,80})", re.IGNORECASE)
    LABEL_TEXT_PATTERN = re.compile(r"<label[^>]*>(?P<value>[^<{]{2,80})", re.IGNORECASE)
    ENDPOINT_PATTERN = re.compile(r"['\"](?P<endpoint>(?:\*\*/)?/(?:api|graphql|v\d)[^'\"]*)['\"]")
    HELPER_PATTERN = re.compile(r"\b(?P<name>(?:mock|stub|build|create|seed)[A-Z][A-Za-z0-9_]*)\b")
    TAG_PATTERN = re.compile(r"@\w[\w-]*")

    @log_performance("playwright_ui_intelligence_service.build")
    def build(
        self,
        repo_path: str,
        inventory: RepositoryInventory,
        repo_profile: RepoProfile,
    ) -> PlaywrightUiContext:
        log_step("playwright_ui_intelligence_started", {"repo_path": repo_path})
        try:
            root = Path(repo_path)
            context = PlaywrightUiContext(
                page_objects=inventory.page_objects,
                fixtures=inventory.fixtures,
                helpers=inventory.helpers,
                ci_commands=self._ci_commands(repo_profile),
                quality_requirements=self._quality_requirements(),
            )
            for path in self._candidate_files(root):
                relative = str(path.relative_to(root))
                content = self._read(path)
                if not content:
                    continue
                is_spec = any(test_file.path == relative for test_file in inventory.test_files)
                self._collect_routes(context, relative, content)
                self._collect_ui_elements(context, relative, content)
                self._collect_mock_patterns(context, relative, content, is_spec)
                self._collect_auth_patterns(context, relative, content, is_spec)
                self._collect_test_data_patterns(context, relative, content)
                if is_spec:
                    context.existing_spec_patterns.append(
                        self._spec_pattern(relative, content)
                    )

            self._trim(context)
            log_metric("ui_route_evidence_count", len(context.routes))
            log_metric("ui_element_evidence_count", len(context.ui_elements))
            log_metric("mock_pattern_count", len(context.mock_patterns))
            log_metric("auth_pattern_count", len(context.auth_session_patterns))
            logger.info("Playwright UI intelligence completed")
            return context
        except Exception as exc:
            log_exception(exc, context={"repo_path": repo_path, "stage": "playwright_ui_intelligence"})
            raise

    def _candidate_files(self, root: Path) -> list[Path]:
        suffixes = {".ts", ".tsx", ".html", ".jsx", ".js", ".mjs", ".cjs"}
        return [
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix in suffixes
            and not self._is_ignored_path(path)
            and path.stat().st_size <= self.MAX_FILE_BYTES
        ]

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def _collect_routes(self, context: PlaywrightUiContext, relative: str, content: str) -> None:
        if not self._looks_like_ui_source(relative):
            return
        for pattern in self.ROUTE_PATTERNS:
            for match in pattern.finditer(content):
                route = match.group("path").strip()
                if route:
                    context.routes.append(
                        UiRouteEvidence(
                            path=route,
                            file_path=relative,
                            line=self._line_number(content, match.start()),
                            reason="Route declaration discovered in UI source.",
                        )
                    )

    def _collect_ui_elements(self, context: PlaywrightUiContext, relative: str, content: str) -> None:
        if not self._looks_like_ui_source(relative):
            return
        for pattern, locator_hint, reason in (
            (self.ARIA_LABEL_PATTERN, "getByLabel", "ARIA label is a stable user-facing locator."),
            (self.TEST_ID_PATTERN, "getByTestId", "data-testid follows a common Playwright convention."),
            (self.PLACEHOLDER_PATTERN, "getByPlaceholder", "Placeholder can identify form inputs."),
            (self.BUTTON_TEXT_PATTERN, "getByRole", "Button text can ground role-based locators."),
            (self.LABEL_TEXT_PATTERN, "getByLabel", "Label text can ground form locators."),
        ):
            for match in pattern.finditer(content):
                text = " ".join(match.group("value").split())
                if not text:
                    continue
                role = "button" if pattern == self.BUTTON_TEXT_PATTERN else None
                context.ui_elements.append(
                    UiElementEvidence(
                        file_path=relative,
                        line=self._line_number(content, match.start()),
                        text=text,
                        role=role,
                        locator_hint=locator_hint,
                        reason=reason,
                    )
                )
        for match in self.ROLE_PATTERN.finditer(content):
            context.ui_elements.append(
                UiElementEvidence(
                    file_path=relative,
                    line=self._line_number(content, match.start()),
                    role=match.group("value"),
                    locator_hint="getByRole",
                    reason="Explicit ARIA role discovered in UI source.",
                )
            )

    def _collect_mock_patterns(
        self,
        context: PlaywrightUiContext,
        relative: str,
        content: str,
        is_spec: bool,
    ) -> None:
        lower = content.lower()
        if "page.route" in content or "route.fulfill" in content:
            for match in self.ENDPOINT_PATTERN.finditer(content):
                context.mock_patterns.append(
                    MockPatternEvidence(
                        kind="playwright_route_stub",
                        file_path=relative,
                        line=self._line_number(content, match.start()),
                        endpoint_or_handler=match.group("endpoint"),
                        reason="Existing Playwright route stubbing pattern.",
                    )
                )
            if "page.route" in content and not any(pattern.file_path == relative for pattern in context.mock_patterns):
                context.mock_patterns.append(
                    MockPatternEvidence(
                        kind="playwright_route_stub",
                        file_path=relative,
                        reason="Existing Playwright route stubbing pattern.",
                    )
                )
        if "msw" in lower or "server.use" in content or "http.get" in content or "graphql." in content:
            context.mock_patterns.append(
                MockPatternEvidence(
                    kind="msw_or_network_handler",
                    file_path=relative,
                    reason="MSW or network handler pattern discovered.",
                )
            )
        if is_spec or any(part in relative.lower() for part in ("mock", "stub", "fixture")):
            for match in self.HELPER_PATTERN.finditer(content):
                name = match.group("name")
                if name.lower().startswith(("mock", "stub")):
                    context.mock_patterns.append(
                        MockPatternEvidence(
                            kind="mock_helper",
                            file_path=relative,
                            line=self._line_number(content, match.start()),
                            helper_name=name,
                            reason="Reusable mock/stub helper discovered.",
                        )
                    )

    def _collect_auth_patterns(
        self,
        context: PlaywrightUiContext,
        relative: str,
        content: str,
        is_spec: bool,
    ) -> None:
        lower = content.lower()
        signals = (
            ("storage_state", "storageState"),
            ("global_setup", "globalSetup"),
            ("login_helper", "login"),
            ("role_or_permission", "permission"),
            ("tenant_or_workspace", "tenant"),
            ("tenant_or_workspace", "workspace"),
        )
        for kind, token in signals:
            if token.lower() in lower:
                context.auth_session_patterns.append(
                    AuthSessionEvidence(
                        kind=kind,
                        file_path=relative,
                        evidence=token,
                        reason="Auth/session setup signal discovered in Playwright UI context.",
                    )
                )
        if is_spec and "test.use" in content:
            context.auth_session_patterns.append(
                AuthSessionEvidence(
                    kind="test_use_fixture",
                    file_path=relative,
                    evidence="test.use",
                    reason="Spec-level fixture/session override discovered.",
                )
            )

    def _collect_test_data_patterns(
        self,
        context: PlaywrightUiContext,
        relative: str,
        content: str,
    ) -> None:
        lower = relative.lower() + "\n" + content.lower()
        if not any(token in lower for token in ("fixture", "factory", "faker", "mock", "seed", "build")):
            return
        for match in self.HELPER_PATTERN.finditer(content):
            name = match.group("name")
            if name.lower().startswith(("build", "create", "seed", "mock")):
                context.test_data_patterns.append(
                    TestDataEvidence(
                        kind="builder_or_fixture",
                        file_path=relative,
                        line=self._line_number(content, match.start()),
                        symbol=name,
                        reason="Reusable UI test data pattern discovered.",
                    )
                )

    def _spec_pattern(self, relative: str, content: str) -> ExistingSpecPattern:
        locator_styles = []
        for token, label in (
            ("getByRole", "role"),
            ("getByLabel", "label"),
            ("getByText", "text"),
            ("getByTestId", "test_id"),
            ("locator(", "raw_locator"),
            ("xpath=", "xpath"),
        ):
            if token in content:
                locator_styles.append(label)
        assertion_styles = []
        for token, label in (
            ("toBeVisible", "visible"),
            ("toHaveText", "text"),
            ("toContainText", "contains_text"),
            ("toHaveURL", "url"),
            ("toHaveValue", "value"),
            ("toBeDisabled", "disabled"),
            ("toBeEnabled", "enabled"),
        ):
            if token in content:
                assertion_styles.append(label)
        setup_hooks = [hook for hook in ("beforeEach", "beforeAll", "afterEach", "afterAll") if hook in content]
        return ExistingSpecPattern(
            file_path=relative,
            locator_styles=locator_styles,
            assertion_styles=assertion_styles,
            uses_page_route="page.route" in content or "route.fulfill" in content,
            uses_msw="server.use" in content or "msw" in content.lower(),
            uses_storage_state="storageState" in content,
            uses_page_objects=bool(re.search(r"\bnew\s+[A-Z][A-Za-z0-9]*Page\b", content)),
            tags=sorted(set(self.TAG_PATTERN.findall(content))),
            setup_hooks=setup_hooks,
        )

    def _ci_commands(self, repo_profile: RepoProfile) -> list[CiCommandEvidence]:
        commands = [
            CiCommandEvidence(command=command, reason="Detected package validation script.")
            for command in repo_profile.validation_commands
            if any(token in command for token in ("e2e", "playwright", "test"))
        ]
        package_manager = repo_profile.package_manager or "npm"
        if not commands and repo_profile.playwright_configs:
            commands.append(
                CiCommandEvidence(
                    command=f"{package_manager} exec playwright test",
                    reason="Fallback Playwright CLI command from detected config.",
                )
            )
        return commands

    def _quality_requirements(self) -> list[QualityRequirement]:
        return [
            QualityRequirement(
                rule="Use existing mocks/stubs/fixtures/auth setup when present.",
                severity="error",
                reason="CI UI tests must be deterministic without real backend dependency.",
            ),
            QualityRequirement(
                rule="Ground every locator in source evidence or existing page object convention.",
                severity="error",
                reason="Invented selectors are the fastest path to flaky generated specs.",
            ),
            QualityRequirement(
                rule="Assert user-visible outcomes, not only object existence or generic visibility.",
                severity="error",
                reason="Assertions should catch production UI regressions.",
            ),
            QualityRequirement(
                rule="Avoid fixed sleeps and timing-sensitive waits.",
                severity="error",
                reason="CI must stay stable under parallel and slower runtime conditions.",
            ),
            QualityRequirement(
                rule="Match existing spec, fixture, tagging, and page-object conventions.",
                severity="warning",
                reason="Repo-native tests are faster for developers to review and maintain.",
            ),
        ]

    def _looks_like_ui_source(self, relative: str) -> bool:
        lower = relative.lower()
        return lower.endswith((".html", ".tsx", ".jsx", ".ts", ".js")) and not lower.endswith((".d.ts",))

    def _line_number(self, content: str, offset: int) -> int:
        return content[: max(offset, 0)].count("\n") + 1

    def _trim(self, context: PlaywrightUiContext) -> None:
        limit = self.MAX_EVIDENCE_PER_KIND
        context.routes = context.routes[:limit]
        context.ui_elements = context.ui_elements[:limit]
        context.mock_patterns = context.mock_patterns[:limit]
        context.auth_session_patterns = context.auth_session_patterns[:limit]
        context.test_data_patterns = context.test_data_patterns[:limit]
        context.existing_spec_patterns = context.existing_spec_patterns[:limit]

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
            "__pycache__",
            ".venv",
        }
        return bool(set(path.parts).intersection(ignored_parts))
