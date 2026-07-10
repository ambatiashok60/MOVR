from __future__ import annotations

from pathlib import PurePosixPath

from app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from app.schemas.execution_target import ExecutionTarget
from app.schemas.llm_outputs import GeneratedTestFileOutput, TestCodeOutput
from app.schemas.repo_profile import RepoProfile
from app.tools.path_safety import resolve_workspace_path
from app.utils.logging_utils import log_step

JAVA_TEST_TOKENS = ("@Test", "org.junit", "org.testng")
PYTHON_TEST_TOKENS = ("def test_", "import pytest", "import unittest", "TestClient")
GENERIC_ASSERTION_TOKENS = (
    "assert",
    "Assert",
    "expect(",
    "andExpect(",
    ".status(",
    "assertThat",
)


class GeneratedFileGuard:
    """Deterministic pre-write review of LLM-generated test files.

    The LLM controls `relative_path`, so without this guard a generated "test"
    could land on — and silently overwrite — application source. Every file must
    be provably a test file (detected test location or per-language test naming),
    must never replace an existing non-test file, must contain test-framework and
    assertion signals for its language, and must match the requested execution
    target. Rejected files are dropped with warnings; surviving warnings feed the
    result's needs_review signal.
    """

    MOCK_TOKENS = (
        "@MockBean",
        "@MockitoBean",
        "Mockito.mock",
        "@Mock",
        "stubFor(",
        "WireMock",
        "MockWebServer",
        "mocker.",
        "monkeypatch",
        "respx",
        "responses.",
    )

    def review(
        self,
        repo_path: str,
        output: TestCodeOutput,
        profile: RepoProfile,
        request: GenerateApiTestCodeRequest,
        mock_stub_plan=None,
    ) -> tuple[TestCodeOutput, list[str], list[str]]:
        kept: list[GeneratedTestFileOutput] = []
        warnings: list[str] = []
        review_reasons: list[str] = []
        root = resolve_workspace_path(repo_path)

        for file in output.files:
            findings = self._file_findings(root, file, profile, request)
            if findings:
                message = f"Rejected generated file `{file.relative_path}`: " + "; ".join(findings)
                warnings.append(message)
                review_reasons.append(message)
                continue
            target = root / file.relative_path
            if target.exists():
                warnings.append(
                    f"Generated file updates existing test `{file.relative_path}`; "
                    "verify the change preserves current coverage."
                )
            kept.append(file)

        mock_finding = self._mock_emission_finding(kept, mock_stub_plan, request)
        if mock_finding:
            warnings.append(mock_finding)
            review_reasons.append(mock_finding)

        if not kept and output.files:
            review_reasons.append(
                "All generated files were rejected by the write guard; deterministic "
                "strategy fallback files were used instead."
            )

        log_step(
            "api_generated_file_guard_completed",
            {
                "input_files": len(output.files),
                "kept_files": len(kept),
                "rejected_files": len(output.files) - len(kept),
            },
        )
        guarded = output.model_copy(update={"files": kept})
        return guarded, warnings, review_reasons

    def _file_findings(
        self,
        root,
        file: GeneratedTestFileOutput,
        profile: RepoProfile,
        request: GenerateApiTestCodeRequest,
    ) -> list[str]:
        findings: list[str] = []
        path = file.relative_path

        if not self._is_test_path(path, profile):
            findings.append(
                "path is not inside a detected test location and does not follow "
                "test naming conventions; refusing to write near application source"
            )
        elif (root / path).exists() and not self._is_test_path(path, profile):
            findings.append("would overwrite an existing non-test file")

        content = file.content or ""
        if not content.strip():
            findings.append("content is empty")
        else:
            if not self._has_framework_signal(path, content):
                findings.append("content has no recognizable test framework signal")
            if not any(token in content for token in GENERIC_ASSERTION_TOKENS):
                findings.append("content contains no assertions")

        if request.execution_target == ExecutionTarget.CI and file.test_target != "ci":
            findings.append("test_target must be ci for a CI-target scenario")
        if request.execution_target == ExecutionTarget.STAGE and file.test_target != "stage":
            findings.append("test_target must be stage for a stage-target scenario")
        return findings

    def _is_test_path(self, path: str, profile: RepoProfile) -> bool:
        normalized = PurePosixPath(path).as_posix()

        # Repo-derived conventions come first: detected team test locations, then
        # the directories the repository's own existing tests live in. Only when
        # the repo teaches us nothing do the universal per-language heuristics
        # below act as the last-resort gate.
        locations = [
            *profile.team_strategy.api_test_locations,
            *profile.team_strategy.stage_test_locations,
            *{
                PurePosixPath(existing.path).parent.as_posix()
                for existing in profile.existing_tests
                if existing.path and PurePosixPath(existing.path).parent.as_posix() != "."
            },
        ]
        for location in locations:
            prefix = PurePosixPath(location).as_posix().rstrip("/")
            if prefix and (normalized == prefix or normalized.startswith(f"{prefix}/")):
                return True

        name = PurePosixPath(normalized).name
        parts = set(PurePosixPath(normalized).parts)
        if normalized.endswith((".java", ".kt")):
            return "src/test/" in normalized or name.endswith(
                ("Test.java", "Tests.java", "IT.java", "Test.kt", "Tests.kt")
            )
        if normalized.endswith(".py"):
            return (
                name.startswith("test_")
                or name.endswith("_test.py")
                or bool(parts.intersection({"tests", "test"}))
            )
        if normalized.endswith((".ts", ".js")):
            return ".spec." in name or ".test." in name or bool(
                parts.intersection({"tests", "test", "e2e"})
            )
        return False

    def _has_framework_signal(self, path: str, content: str) -> bool:
        if path.endswith((".java", ".kt")):
            return any(token in content for token in JAVA_TEST_TOKENS)
        if path.endswith(".py"):
            return any(token in content for token in PYTHON_TEST_TOKENS)
        return True  # other languages: rely on the assertion check only

    def _mock_emission_finding(
        self,
        kept: list[GeneratedTestFileOutput],
        mock_stub_plan,
        request: GenerateApiTestCodeRequest,
    ) -> str | None:
        """The mock/stub plan is a promise, not advice: CI tests generated for a
        plan that names dependencies to mock must contain mocking/stubbing, or
        they will hit real downstream services and flake."""
        if mock_stub_plan is None or not getattr(
            mock_stub_plan, "dependencies_to_mock", None
        ):
            return None
        ci_content = "\n".join(
            file.content for file in kept if file.test_target == "ci"
        )
        if not ci_content:
            return None
        if any(token in ci_content for token in self.MOCK_TOKENS):
            return None
        names = ", ".join(
            dep.name for dep in mock_stub_plan.dependencies_to_mock[:5]
        )
        return (
            "Mock emission gap: the mock/stub plan requires mocking dependencies "
            f"({names}) but the generated CI tests contain no mocking or stubbing; "
            "they would hit real downstream services."
        )
