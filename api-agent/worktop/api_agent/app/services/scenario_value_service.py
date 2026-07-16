from __future__ import annotations

import logging
import re
from pathlib import Path

from worktop.api_agent.app.coverage.api_coverage_service import ApiCoverageService
from worktop.api_agent.app.schemas.api_scenario import ApiScenario
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.scenario_value import (
    ScenarioValueAssessment,
    ScenarioValueReport,
    ScenarioValueVerdict,
)
from worktop.api_agent.utils.logging import get_logger

logger = get_logger(__name__)

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")
_STOPWORDS = {
    "the", "and", "with", "that", "this", "then", "for", "from", "into",
    "should", "must", "will", "when", "verify", "check", "ensure", "returns",
    "response", "request", "api", "test", "scenario",
}
_MAX_EXISTING_FILES = 40


class ScenarioValueService:
    """Score whether generated scenarios add value over existing coverage.

    A scenario is compared against the repository's existing API tests and
    against the other scenarios in the same batch. A FULL_DUPLICATE is never
    accepted silently, and the same verdicts power the Consolidate action that
    dedupes a scenario list.
    """

    def __init__(self) -> None:
        self.coverage = ApiCoverageService()

    def evaluate(
        self,
        scenarios: list[ApiScenario],
        profile: RepoProfile,
    ) -> ScenarioValueReport:
        existing = self._existing_signatures(profile)
        assessments: list[ScenarioValueAssessment] = []
        earlier: list[tuple[ApiScenario, set[str]]] = []
        for scenario in scenarios:
            signals = self._signals(scenario)
            assessment = self._assess(scenario, signals, existing, earlier)
            assessments.append(assessment)
            earlier.append((scenario, signals))

        requires_approval = any(
            assessment.verdict == "FULL_DUPLICATE" for assessment in assessments
        )
        verdicts = sorted({assessment.verdict for assessment in assessments})
        report = ScenarioValueReport(
            assessments=assessments,
            requires_approval=requires_approval,
            summary=(
                f"{len(assessments)} scenario(s): {', '.join(verdicts)}"
                if assessments
                else "No scenarios to evaluate."
            ),
        )
        logger.log(
            logging.WARNING if requires_approval else logging.INFO,
            "Scenario value analysis: %s%s",
            report.summary,
            " — full duplicates require approval" if requires_approval else "",
        )
        return report

    def consolidate(
        self,
        scenarios: list[ApiScenario],
        report: ScenarioValueReport | None = None,
        profile: RepoProfile | None = None,
    ) -> tuple[list[ApiScenario], list[ScenarioValueAssessment]]:
        """Drop FULL_DUPLICATE scenarios; returns (kept, dropped assessments)."""
        if report is None:
            report = self.evaluate(scenarios, profile or RepoProfile(repo_path=""))
        verdict_by_id = {a.api_scenario_id: a for a in report.assessments}
        kept: list[ApiScenario] = []
        dropped: list[ScenarioValueAssessment] = []
        for scenario in scenarios:
            assessment = verdict_by_id.get(scenario.api_scenario_id)
            if assessment is not None and assessment.verdict == "FULL_DUPLICATE":
                dropped.append(assessment)
            else:
                kept.append(scenario)
        logger.info(
            "Consolidated %s scenario(s) down to %s (%s duplicate(s) removed).",
            len(scenarios),
            len(kept),
            len(dropped),
        )
        return kept, dropped

    def review_reasons(self, report: ScenarioValueReport) -> list[str]:
        reasons: list[str] = []
        for assessment in report.assessments:
            if assessment.verdict == "FULL_DUPLICATE":
                source = (
                    "existing test"
                    if assessment.duplicate_source == "existing_test"
                    else "scenario"
                )
                reasons.append(
                    f"Scenario '{assessment.api_scenario_id}' fully duplicates "
                    f"{source} '{assessment.duplicate_of}'; approval required "
                    "before generating a duplicate."
                )
            elif assessment.verdict == "LOW_VALUE":
                reasons.append(
                    f"Scenario '{assessment.api_scenario_id}' asserts nothing "
                    "meaningful and is low value."
                )
        return reasons

    def _assess(
        self,
        scenario: ApiScenario,
        signals: set[str],
        existing: list[tuple[str, set[str]]],
        earlier: list[tuple[ApiScenario, set[str]]],
    ) -> ScenarioValueAssessment:
        best_overlap = 0.0
        duplicate_of: str | None = None
        duplicate_source: str | None = None
        for path, existing_signals in existing:
            overlap = self._jaccard(signals, existing_signals)
            if overlap > best_overlap:
                best_overlap, duplicate_of, duplicate_source = (
                    overlap, path, "existing_test",
                )
        for other, other_signals in earlier:
            overlap = self._jaccard(signals, other_signals)
            if overlap > best_overlap:
                best_overlap, duplicate_of, duplicate_source = (
                    overlap, other.api_scenario_id, "generated_scenario",
                )

        verdict = self._verdict(scenario, best_overlap)
        return ScenarioValueAssessment(
            api_scenario_id=scenario.api_scenario_id,
            scenario_name=scenario.scenario_name,
            verdict=verdict,
            overlap=round(best_overlap, 3),
            duplicate_of=duplicate_of if verdict.endswith("DUPLICATE") else None,
            duplicate_source=(
                duplicate_source if verdict.endswith("DUPLICATE") else None
            ),  # type: ignore[arg-type]
            rationale=(
                f"Signal overlap {best_overlap:.2f} with "
                f"{duplicate_source or 'nothing comparable'} "
                f"'{duplicate_of or '-'}' → {verdict}."
            ),
        )

    def _verdict(self, scenario: ApiScenario, overlap: float) -> ScenarioValueVerdict:
        if not scenario.assertions:
            return "LOW_VALUE"
        if overlap >= 0.85:
            return "FULL_DUPLICATE"
        if overlap >= 0.55:
            return "PARTIAL_DUPLICATE"
        if overlap >= 0.25:
            return "MEANINGFUL_VARIATION"
        return "NEW_COVERAGE"

    def _signals(self, scenario: ApiScenario) -> set[str]:
        signals: set[str] = set()
        if scenario.endpoint:
            signals.add(f"endpoint:{scenario.endpoint}")
        if scenario.method:
            signals.add(f"method:{scenario.method.upper()}")
        signals.update(
            f"assert:{token}"
            for assertion in scenario.assertions
            for token in self._tokens(assertion)
        )
        signals.update(
            f"step:{token}"
            for step in scenario.scenario_steps
            for token in self._tokens(step)
        )
        signals.add(f"type:{scenario.scenario_type}")
        return signals

    def _existing_signatures(self, profile: RepoProfile) -> list[tuple[str, set[str]]]:
        root = Path(profile.repo_path) if profile.repo_path else None
        signatures: list[tuple[str, set[str]]] = []
        if root is None or not root.exists():
            return signatures
        for candidate in profile.existing_tests[:_MAX_EXISTING_FILES]:
            target = root / candidate.path
            if not target.is_file():
                continue
            entry = self.coverage.entry_from_source(
                candidate.path, target.read_text(encoding="utf-8", errors="ignore")
            )
            signals = {
                *(f"endpoint:{endpoint}" for endpoint in entry.endpoints),
                *(f"assert:{token}"
                  for body in entry.body_assertions
                  for token in self._tokens(body)),
                *(f"assert:{status}" for status in entry.status_assertions),
            }
            if signals:
                signatures.append((candidate.path, signals))
        return signatures

    def _tokens(self, text: str) -> set[str]:
        return {
            token.lower()
            for token in _TOKEN_PATTERN.findall(text)
            if len(token) > 2 and token.lower() not in _STOPWORDS
        }

    def _jaccard(self, left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)
