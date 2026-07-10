from __future__ import annotations

import logging

from app.coverage.coverage_preservation_service import CoveragePreservationService
from app.logging_config import log_event
from app.schemas.behavioral_test_unit import BehavioralTestUnit
from app.schemas.code_patch import PatchSet
from app.schemas.coverage import BehaviorCoverageEntry
from app.schemas.test_value import TestValueAssessment, TestValueReport, TestValueVerdict
from app.tools.playwright_parser_tool import PlaywrightParserTool

logger = logging.getLogger(__name__)

_SPEC_SUFFIXES = (".spec.ts", ".spec.tsx", ".e2e.ts", ".e2e.tsx", ".pw.ts", ".playwright.ts")


class TestValueService:
    """Score whether generated tests add value over the existing inventory.

    A generated test that compiles is not necessarily useful: it may re-verify
    behavior an existing test already covers with a different implementation.
    Each generated test is compared against the closest existing test by
    behavioral signal overlap and classified; a FULL_DUPLICATE is never
    accepted silently — it requires explicit approval.
    """

    __test__ = False  # "Test" prefix is domain naming, not a pytest class

    def __init__(self) -> None:
        self.parser = PlaywrightParserTool()
        self.signals = CoveragePreservationService()

    def evaluate(
        self,
        patches: PatchSet,
        existing: list[BehavioralTestUnit],
    ) -> TestValueReport:
        existing_entries = self.signals.snapshot(existing)
        existing_titles = {
            (unit.file_path, unit.test_title) for unit in existing
        }
        assessments: list[TestValueAssessment] = []
        for patch in patches.patches:
            if not patch.path.endswith(_SPEC_SUFFIXES):
                continue
            for unit in self.parser.extract_tests(patch.path, patch.content):
                if (unit.file_path, unit.test_title) in existing_titles:
                    # A re-emitted existing test (extension) is judged by the
                    # coverage-preservation engine, not as a new test.
                    continue
                entry = self.signals.snapshot([unit])[0]
                assessments.append(self._assess(entry, existing_entries))

        requires_approval = any(
            assessment.verdict == "FULL_DUPLICATE" for assessment in assessments
        )
        verdicts = sorted({assessment.verdict for assessment in assessments})
        report = TestValueReport(
            assessments=assessments,
            requires_approval=requires_approval,
            summary=(
                f"{len(assessments)} generated test(s): {', '.join(verdicts)}"
                if assessments
                else "No newly generated tests to evaluate."
            ),
        )
        log_event(
            logger,
            logging.WARNING if requires_approval else logging.INFO,
            "test_value_analysis",
            "requires_approval" if requires_approval else "completed",
            tests=len(assessments),
            verdicts=verdicts,
        )
        return report

    def review_reasons(
        self,
        report: TestValueReport,
        *,
        allow_full_duplicates: bool = False,
    ) -> list[str]:
        reasons: list[str] = []
        for assessment in report.assessments:
            if assessment.verdict == "FULL_DUPLICATE" and not allow_full_duplicates:
                reasons.append(
                    f"Generated test '{assessment.test_title}' fully duplicates "
                    f"'{assessment.closest_existing_test}' in "
                    f"{assessment.closest_existing_file}; approval required before "
                    "accepting a duplicate."
                )
            elif assessment.verdict == "LOW_VALUE":
                reasons.append(
                    f"Generated test '{assessment.test_title}' asserts nothing "
                    "meaningful and is low value; manual review recommended."
                )
        return reasons

    def _assess(
        self,
        entry: BehaviorCoverageEntry,
        existing: list[BehaviorCoverageEntry],
    ) -> TestValueAssessment:
        # Generic interaction kinds (click/fill/…) appear in almost every test
        # and would make unrelated tests look similar, so overlap is computed
        # over the outcome-bearing signals only.
        signals = self._value_signals(entry)
        closest: BehaviorCoverageEntry | None = None
        closest_overlap = 0.0
        for candidate in existing:
            overlap = self._jaccard(signals, self._value_signals(candidate))
            if overlap > closest_overlap or closest is None:
                closest = candidate
                closest_overlap = overlap

        closest_signals = self._value_signals(closest) if closest else set()
        new_signals = signals - closest_signals
        duplicated = signals & closest_signals
        verdict = self._verdict(entry, signals, new_signals, closest_overlap)
        return TestValueAssessment(
            file_path=entry.file_path,
            test_title=entry.test_title,
            verdict=verdict,
            behavior_overlap=round(closest_overlap, 3),
            new_assertions=sorted(
                signal.removeprefix("assert:")
                for signal in new_signals
                if signal.startswith("assert:")
            ),
            duplicated_assertions=sorted(
                signal.removeprefix("assert:")
                for signal in duplicated
                if signal.startswith("assert:")
            ),
            new_navigations=sorted(
                signal.removeprefix("nav:")
                for signal in new_signals
                if signal.startswith("nav:")
            ),
            new_data_inputs=self._new_data_inputs(entry, closest),
            closest_existing_test=closest.test_title if closest else None,
            closest_existing_file=closest.file_path if closest else None,
            rationale=self._rationale(verdict, closest, closest_overlap),
        )

    def _verdict(
        self,
        entry: BehaviorCoverageEntry,
        signals: set[str],
        new_signals: set[str],
        overlap: float,
    ) -> TestValueVerdict:
        if not entry.assertions:
            return "LOW_VALUE"
        if overlap >= 0.9 and not new_signals:
            return "FULL_DUPLICATE"
        if overlap >= 0.5:
            return "PARTIAL_DUPLICATE"
        if overlap >= 0.2:
            return "MEANINGFUL_VARIATION"
        return "NEW_COVERAGE"

    def _new_data_inputs(
        self,
        entry: BehaviorCoverageEntry,
        closest: BehaviorCoverageEntry | None,
    ) -> list[str]:
        existing_inputs = set(closest.data_inputs) if closest else set()
        return sorted(set(entry.data_inputs) - existing_inputs)

    def _rationale(
        self,
        verdict: TestValueVerdict,
        closest: BehaviorCoverageEntry | None,
        overlap: float,
    ) -> str:
        if closest is None:
            return "No existing tests to compare against; treated as new coverage."
        return (
            f"Behavioral signal overlap {overlap:.2f} with closest existing test "
            f"'{closest.test_title}' ({closest.file_path}) → {verdict}."
        )

    def _value_signals(self, entry: BehaviorCoverageEntry) -> set[str]:
        return {
            signal
            for signal in entry.signals()
            if not signal.startswith("interact:")
        }

    def _jaccard(self, left: set[str], right: set[str]) -> float:
        if not left and not right:
            return 1.0
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)
