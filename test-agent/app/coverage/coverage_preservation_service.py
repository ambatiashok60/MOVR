from __future__ import annotations

import logging
import re
from pathlib import Path

from app.logging_config import log_event
from app.schemas.behavioral_test_unit import BehavioralTestUnit
from app.schemas.code_patch import PatchSet
from app.schemas.coverage import (
    BehaviorCoverageEntry,
    CoverageModification,
    CoveragePreservationReport,
)
from app.tools.playwright_parser_tool import PlaywrightParserTool

logger = logging.getLogger(__name__)

_ASSERTION_PATTERN = re.compile(r"expect(?:\.soft)?\s*\(([^;]{0,160}?)\)\s*\.\s*(\w+)")
_NAVIGATION_PATTERN = re.compile(r"\.goto\s*\(\s*['\"`]([^'\"`]+)['\"`]")
_API_PATTERN = re.compile(
    r"(?:waitForResponse|route|request\.(?:get|post|put|patch|delete|fetch))"
    r"\s*\(\s*['\"`]?([^'\"`,)]*)"
)
_INTERACTION_PATTERN = re.compile(r"\.(click|fill|check|uncheck|selectOption|press|hover)\s*\(")
_DATA_INPUT_PATTERN = re.compile(
    r"\.(?:fill|type|selectOption)\s*\([^,)]*,\s*['\"`]([^'\"`]+)['\"`]"
)


class CoveragePreservationService:
    """Prove that existing behavioral coverage survives generation.

    Builds a coverage graph before generation (from the behavioral inventory)
    and after generation (by re-parsing every patched spec file), then compares
    the graphs so lost coverage is detected instead of assumed away.
    """

    def __init__(self) -> None:
        self.parser = PlaywrightParserTool()

    def snapshot(self, units: list[BehavioralTestUnit]) -> list[BehaviorCoverageEntry]:
        return [self._entry_from_unit(unit) for unit in units]

    def snapshot_after_patches(
        self,
        repo_path: str,
        patches: PatchSet,
        before: list[BehaviorCoverageEntry],
    ) -> list[BehaviorCoverageEntry]:
        """Coverage graph after generation.

        Patched spec files are re-read from disk and re-parsed; files the patch
        set never touched keep their pre-generation entries.
        """
        patched_paths = {patch.path for patch in patches.patches}
        after = [entry for entry in before if entry.file_path not in patched_paths]
        root = Path(repo_path)
        for path in sorted(patched_paths):
            target = root / path
            if not target.is_file():
                continue
            content = target.read_text(encoding="utf-8", errors="ignore")
            for unit in self.parser.extract_tests(path, content):
                after.append(self._entry_from_unit(unit))
        return after

    def compare(
        self,
        before: list[BehaviorCoverageEntry],
        after: list[BehaviorCoverageEntry],
    ) -> CoveragePreservationReport:
        before_map = {entry.coverage_key: entry for entry in before}
        after_map = {entry.coverage_key: entry for entry in after}

        removed = [
            entry for key, entry in before_map.items() if key not in after_map
        ]
        added = [entry for key, entry in after_map.items() if key not in before_map]
        preserved: list[BehaviorCoverageEntry] = []
        modified: list[CoverageModification] = []
        for key, entry in before_map.items():
            counterpart = after_map.get(key)
            if counterpart is None:
                continue
            lost = sorted(entry.signals() - counterpart.signals())
            gained = sorted(counterpart.signals() - entry.signals())
            if lost or gained:
                modified.append(
                    CoverageModification(
                        file_path=entry.file_path,
                        test_title=entry.test_title,
                        lost_signals=lost,
                        gained_signals=gained,
                    )
                )
            else:
                preserved.append(counterpart)

        lost_behavior = bool(removed) or any(item.lost_signals for item in modified)
        report = CoveragePreservationReport(
            preserved=preserved,
            added=added,
            removed=removed,
            modified=modified,
            coverage_preserved=not lost_behavior,
            summary=self._summarize(preserved, added, removed, modified),
        )
        log_event(
            logger,
            logging.WARNING if lost_behavior else logging.INFO,
            "coverage_preservation",
            "coverage_lost" if lost_behavior else "coverage_preserved",
            preserved=len(preserved),
            added=len(added),
            removed=len(removed),
            modified=len(modified),
        )
        return report

    def review_reasons(self, report: CoveragePreservationReport) -> list[str]:
        reasons: list[str] = []
        for entry in report.removed:
            reasons.append(
                f"Coverage lost: existing test '{entry.test_title}' in "
                f"{entry.file_path} no longer exists after generation."
            )
        for item in report.modified:
            if not item.lost_signals:
                continue
            reasons.append(
                f"Coverage weakened: test '{item.test_title}' in {item.file_path} "
                f"lost behavioral signals {item.lost_signals}."
            )
        return reasons

    def _entry_from_unit(self, unit: BehavioralTestUnit) -> BehaviorCoverageEntry:
        source = unit.source_excerpt or ""
        assertions = [
            f"{subject.strip()}.{matcher}"
            for subject, matcher in _ASSERTION_PATTERN.findall(source)
        ]
        navigations = _NAVIGATION_PATTERN.findall(source)
        api_calls = [match for match in _API_PATTERN.findall(source) if match]
        interactions = sorted({match for match in _INTERACTION_PATTERN.findall(source)})
        data_inputs = sorted({match for match in _DATA_INPUT_PATTERN.findall(source)})
        return BehaviorCoverageEntry(
            file_path=unit.file_path,
            describe_title=unit.describe_title,
            test_title=unit.test_title,
            assertions=assertions,
            navigations=navigations,
            api_calls=api_calls,
            interactions=interactions,
            data_inputs=data_inputs,
            page_objects=unit.page_objects,
            fixtures=unit.fixtures,
        )

    def _summarize(
        self,
        preserved: list[BehaviorCoverageEntry],
        added: list[BehaviorCoverageEntry],
        removed: list[BehaviorCoverageEntry],
        modified: list[CoverageModification],
    ) -> list[str]:
        summary = [
            *(f"Preserved: {entry.test_title}" for entry in preserved),
            *(f"Added: {entry.test_title}" for entry in added),
            *(f"Removed: {entry.test_title}" for entry in removed),
            *(
                f"Modified: {item.test_title} "
                f"(lost {len(item.lost_signals)}, gained {len(item.gained_signals)})"
                for item in modified
            ),
        ]
        if not removed and not any(item.lost_signals for item in modified):
            summary.append("Removed: none")
        return summary
