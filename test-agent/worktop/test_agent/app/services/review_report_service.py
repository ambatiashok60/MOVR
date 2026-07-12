from __future__ import annotations

import logging
import re
from typing import Any

from worktop.test_agent.app.schemas.behavioral_test_unit import AnchorFlowContext, ExistingTestContext
from worktop.test_agent.app.schemas.code_patch import PatchSet, PatchWriteResult
from worktop.test_agent.app.schemas.coverage import CoveragePreservationReport
from worktop.test_agent.app.schemas.generation_request import GenerationRequest
from worktop.test_agent.app.schemas.review_report import ReviewFileChange, ReviewReport
from worktop.test_agent.app.schemas.test_value import TestValueReport
from worktop.test_agent.app.schemas.traceability import TraceabilityMatrix
from worktop.test_agent.app.schemas.validation_result import ValidationResult
from worktop.core_services.app.utility.custom_logger.logging import logger


_SPEC_SUFFIXES = (".spec.ts", ".spec.tsx", ".e2e.ts", ".e2e.tsx", ".pw.ts", ".playwright.ts")
_METHOD_DECLARATION_PATTERN = re.compile(
    r"^\s*(?:public\s+|private\s+|protected\s+)?(?:async\s+)?(\w+)\s*\([^)]*\)\s*[:{]",
    re.MULTILINE,
)
_METHOD_CALL_PATTERN = re.compile(r"\b(\w+)\.(\w+)\s*\(")
_ASSERTION_LINE_PATTERN = re.compile(r"^.*\bexpect(?:\.soft)?\s*\(.*$", re.MULTILINE)
_GENERIC_RECEIVERS = {"page", "expect", "test", "console", "this", "request", "browser"}


class ReviewReportService:
    """Condense a generation run into a five-minute developer review report."""

    def build(
        self,
        request: GenerationRequest,
        *,
        placement: Any | None = None,
        action: Any | None = None,
        flow_plan: Any | None = None,
        anchor_flow_context: AnchorFlowContext | None = None,
        existing_test_context: ExistingTestContext | None = None,
        locator_decisions: Any | None = None,
        patches: PatchSet | None = None,
        patch_result: PatchWriteResult | None = None,
        validation: ValidationResult | None = None,
        coverage: CoveragePreservationReport | None = None,
        test_value: TestValueReport | None = None,
        traceability: TraceabilityMatrix | None = None,
        review_reasons: list[str] | None = None,
    ) -> ReviewReport:
        patches = patches or PatchSet()
        risks = list(review_reasons or [])

        report = ReviewReport(
            summary=self._summary(request, action, patches, patch_result),
            files_changed=[
                ReviewFileChange(
                    path=patch.path, operation=patch.operation, reason=patch.reason
                )
                for patch in patches.patches
            ],
            flows_reused=self._flows_reused(anchor_flow_context, existing_test_context, flow_plan),
            flows_added=self._flows_added(flow_plan, coverage),
            action=getattr(action, "action", "") or "",
            action_rationale=self._trace_justification(action),
            placement_rationale=self._trace_justification(placement),
            methods_created=self._methods_created(patches),
            methods_reused=self._methods_reused(patches),
            locators_reused=self._locators_reused(locator_decisions),
            assertions_added=self._assertions_added(patches),
            validation_summary=self._validation_summary(validation),
            remaining_risks=risks,
        )
        report.markdown = self._render_markdown(report, test_value, traceability, coverage)
        logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'review_report', 'built', {'files': len(report.files_changed), 'risks': len(report.remaining_risks)})
        return report

    def _summary(
        self,
        request: GenerationRequest,
        action: Any | None,
        patches: PatchSet,
        patch_result: PatchWriteResult | None,
    ) -> str:
        action_name = getattr(action, "action", None) or "generation"
        applied = len(patch_result.applied) if patch_result else 0
        return (
            f"'{request.test_case_name}' generated via {action_name}: "
            f"{len(patches.patches)} patch(es) planned, {applied} applied."
        )

    def _trace_justification(self, decision: Any | None) -> str:
        trace = getattr(decision, "decision_trace", None)
        return (getattr(trace, "justification", "") or "").strip()

    def _flows_reused(
        self,
        anchor: AnchorFlowContext | None,
        existing: ExistingTestContext | None,
        flow_plan: Any | None,
    ) -> list[str]:
        flows: list[str] = []
        if existing is not None:
            flows.append(
                f"Extended existing test '{existing.test_title}' in {existing.file_path}"
            )
        if anchor is not None:
            flows.append(
                f"Anchored on '{anchor.anchor_test_title}' in {anchor.file_path} "
                f"(page objects: {', '.join(anchor.page_objects) or 'none'})"
            )
        for step in getattr(flow_plan, "preserved_steps", None) or []:
            flows.append(f"Preserved step: {step}")
        return flows

    def _flows_added(
        self,
        flow_plan: Any | None,
        coverage: CoveragePreservationReport | None,
    ) -> list[str]:
        flows = [
            f"Added step: {step}"
            for step in (getattr(flow_plan, "added_steps", None) or [])
        ]
        if coverage is not None:
            flows.extend(
                f"Added test: {entry.test_title} ({entry.file_path})"
                for entry in coverage.added
            )
        return flows

    def _methods_created(self, patches: PatchSet) -> list[str]:
        created: list[str] = []
        for patch in patches.patches:
            if patch.path.endswith(_SPEC_SUFFIXES) or not patch.path.endswith(
                (".ts", ".tsx")
            ):
                continue
            for name in _METHOD_DECLARATION_PATTERN.findall(patch.content):
                if name not in {"constructor", "if", "for", "while", "switch", "catch"}:
                    created.append(f"{patch.path}: {name}()")
        return created

    def _methods_reused(self, patches: PatchSet) -> list[str]:
        created_names = {
            entry.split(": ")[-1].removesuffix("()")
            for entry in self._methods_created(patches)
        }
        reused: list[str] = []
        for patch in patches.patches:
            if not patch.path.endswith(_SPEC_SUFFIXES):
                continue
            for receiver, method in _METHOD_CALL_PATTERN.findall(patch.content):
                if receiver in _GENERIC_RECEIVERS or method in created_names:
                    continue
                entry = f"{receiver}.{method}()"
                if entry not in reused:
                    reused.append(entry)
        return reused

    def _locators_reused(self, locator_decisions: Any | None) -> list[str]:
        decisions = getattr(locator_decisions, "decisions", None) or []
        return [
            f"{decision.locator} ({decision.reason})" if decision.reason else decision.locator
            for decision in decisions
        ]

    def _assertions_added(self, patches: PatchSet) -> list[str]:
        assertions: list[str] = []
        for patch in patches.patches:
            if not patch.path.endswith(_SPEC_SUFFIXES):
                continue
            for line in _ASSERTION_LINE_PATTERN.findall(patch.content):
                stripped = line.strip()
                if stripped not in assertions:
                    assertions.append(stripped)
        return assertions

    def _validation_summary(self, validation: ValidationResult | None) -> str:
        if validation is None:
            return "Validation was not run."
        failed = [check.name for check in validation.checks if not check.passed]
        if validation.passed:
            return f"Validation passed ({len(validation.checks)} check(s))."
        return (
            f"Validation FAILED; failing checks: {', '.join(failed) or 'unknown'}"
            + (" (repair attempted)." if validation.repair_attempted else ".")
        )

    def _render_markdown(
        self,
        report: ReviewReport,
        test_value: TestValueReport | None,
        traceability: TraceabilityMatrix | None,
        coverage: CoveragePreservationReport | None,
    ) -> str:
        def section(title: str, items: list[str], empty: str = "None") -> str:
            body = "\n".join(f"- {item}" for item in items) if items else f"- {empty}"
            return f"## {title}\n{body}"

        parts = [
            f"# Generation Review Report\n\n{report.summary}",
            section(
                "Files Changed",
                [
                    f"`{change.path}` ({change.operation})"
                    + (f" — {change.reason}" if change.reason else "")
                    for change in report.files_changed
                ],
            ),
            section("Flow Reused", report.flows_reused),
            section("Flow Added", report.flows_added),
            f"## Why {report.action or 'this action'}\n"
            f"{report.action_rationale or 'No rationale recorded.'}",
            f"## Why this placement\n"
            f"{report.placement_rationale or 'No rationale recorded.'}",
            section("Methods Reused", report.methods_reused),
            section("Methods Created", report.methods_created),
            section("Locators Reused", report.locators_reused),
            section("Assertions Added", report.assertions_added),
            f"## Validation\n{report.validation_summary}",
        ]
        if coverage is not None:
            parts.append(section("Coverage", coverage.summary))
        if test_value is not None:
            parts.append(
                section(
                    "Test Value",
                    [
                        f"{assessment.test_title}: {assessment.verdict} — {assessment.rationale}"
                        for assessment in test_value.assessments
                    ],
                    empty=test_value.summary,
                )
            )
        if traceability is not None:
            parts.append(section("Requirement Traceability", traceability.summary))
        parts.append(
            section("Remaining Risks", report.remaining_risks, empty="None identified")
        )
        return "\n\n".join(parts) + "\n"
