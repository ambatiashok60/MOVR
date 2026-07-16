from __future__ import annotations

import re
from pathlib import Path

from worktop.api_agent.app.schemas.api_test_generation_request import (
    GenerateApiTestCodeRequest,
)
from worktop.api_agent.app.schemas.coverage import ApiCoverageReport
from worktop.api_agent.app.schemas.generated_file import GeneratedFile
from worktop.api_agent.app.schemas.mock_stub_plan import MockStubPlan
from worktop.api_agent.app.schemas.review_report import (
    ApiReviewReport,
    ReviewFileChange,
)
from worktop.api_agent.app.schemas.traceability import TraceabilityMatrix
from worktop.api_agent.app.schemas.validation_result import ValidationResult
from worktop.api_agent.utils.logging import get_logger

logger = get_logger(__name__)

_ASSERTION_LINE_PATTERN = re.compile(
    r"^.*(?:\.then\(\)|andExpect|assert\w*\(|expect\(|statusCode\(|jsonPath\().*$",
    re.MULTILINE,
)


class ReviewReportService:
    """Condense an API test generation run into a five-minute review report."""

    def build(
        self,
        request: GenerateApiTestCodeRequest,
        *,
        generated_files: list[GeneratedFile],
        strategy_name: str | None = None,
        strategy_reasons: list[str] | None = None,
        mock_stub_plan: MockStubPlan | None = None,
        reused_example_paths: list[str] | None = None,
        validation: ValidationResult | None = None,
        coverage: ApiCoverageReport | None = None,
        traceability: TraceabilityMatrix | None = None,
        review_reasons: list[str] | None = None,
    ) -> ApiReviewReport:
        report = ApiReviewReport(
            summary=(
                f"Scenario '{request.scenario_name}' "
                f"({request.method or '?'} {request.endpoint or '?'}, "
                f"target {request.execution_target}): "
                f"{len(generated_files)} file(s) generated."
            ),
            files_changed=[
                ReviewFileChange(
                    path=file.path,
                    operation=file.operation,
                    test_target=file.test_target,
                    summary=file.summary,
                )
                for file in generated_files
            ],
            strategy=strategy_name or "unknown",
            strategy_rationale=list(strategy_reasons or []),
            mocks_planned=self._mocks(mock_stub_plan),
            examples_reused=list(reused_example_paths or []),
            assertions_added=self._assertions(request.repo_path, generated_files),
            validation_summary=self._validation_summary(validation),
            remaining_risks=list(review_reasons or []),
        )
        report.markdown = self._render_markdown(report, coverage, traceability)
        logger.info(
            "Review report built: %s file(s), %s risk(s).",
            len(report.files_changed),
            len(report.remaining_risks),
        )
        return report

    def _mocks(self, plan: MockStubPlan | None) -> list[str]:
        if plan is None:
            return []
        entries: list[str] = []
        for field_name, value in plan.model_dump().items():
            if isinstance(value, list):
                entries.extend(f"{field_name}: {item}" for item in value[:10])
            elif value:
                entries.append(f"{field_name}: {value}")
        return entries

    def _assertions(
        self, repo_path: str, generated_files: list[GeneratedFile]
    ) -> list[str]:
        root = Path(repo_path)
        assertions: list[str] = []
        for file in generated_files:
            target = root / file.path
            if not target.is_file():
                continue
            source = target.read_text(encoding="utf-8", errors="ignore")
            for line in _ASSERTION_LINE_PATTERN.findall(source):
                stripped = line.strip()
                if stripped and stripped not in assertions:
                    assertions.append(stripped)
        return assertions[:40]

    def _validation_summary(self, validation: ValidationResult | None) -> str:
        if validation is None:
            return "Validation was not run."
        if validation.passed:
            return f"Validation passed: {validation.summary}"
        return f"Validation FAILED: {validation.summary}"

    def _render_markdown(
        self,
        report: ApiReviewReport,
        coverage: ApiCoverageReport | None,
        traceability: TraceabilityMatrix | None,
    ) -> str:
        def section(title: str, items: list[str], empty: str = "None") -> str:
            body = "\n".join(f"- {item}" for item in items) if items else f"- {empty}"
            return f"## {title}\n{body}"

        parts = [
            f"# API Generation Review Report\n\n{report.summary}",
            section(
                "Files Changed",
                [
                    f"`{change.path}` ({change.operation}, {change.test_target})"
                    + (f" — {change.summary}" if change.summary else "")
                    for change in report.files_changed
                ],
            ),
            f"## Strategy\n{report.strategy}",
            section("Why this strategy", report.strategy_rationale),
            section("Mocks & Stubs Planned", report.mocks_planned),
            section("Examples Reused", report.examples_reused),
            section("Assertions Added", report.assertions_added),
            f"## Validation\n{report.validation_summary}",
        ]
        if coverage is not None:
            parts.append(section("Coverage", coverage.summary))
        if traceability is not None:
            parts.append(section("Requirement Traceability", traceability.summary))
        parts.append(
            section("Remaining Risks", report.remaining_risks, empty="None identified")
        )
        return "\n\n".join(parts) + "\n"
