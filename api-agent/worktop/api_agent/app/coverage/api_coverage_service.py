from __future__ import annotations

import logging
import re
from pathlib import Path

from worktop.api_agent.app.schemas.coverage import (
    ApiCoverageEntry,
    ApiCoverageModification,
    ApiCoverageReport,
)
from worktop.api_agent.utils.logging import get_logger

logger = get_logger(__name__)

_ENDPOINT_PATTERNS = (
    # RestAssured / Spring MockMvc / requests / httpx styles
    re.compile(r"\b(?:get|post|put|patch|delete|head|options)\s*\(\s*['\"]([/{][^'\"]*)['\"]", re.I),
    re.compile(r"\.(?:get|post|put|patch|delete)\s*\(\s*['\"](https?://[^'\"]+|/[^'\"]*)['\"]", re.I),
)
_STATUS_PATTERNS = (
    re.compile(r"statusCode\s*\(\s*(\d{3})\s*\)"),
    re.compile(r"status\(\)\.(is\w+|is\s*\(\s*\d{3}\s*\))"),
    re.compile(r"status_code\s*==\s*(\d{3})"),
    re.compile(r"\.status\s*\(\s*(\d{3})\s*\)"),
)
_BODY_PATTERNS = (
    re.compile(r"\bbody\s*\(\s*['\"]([^'\"]{1,80})['\"]"),
    re.compile(r"jsonPath\s*\(\s*['\"]([^'\"]{1,80})['\"]"),
    re.compile(r"matchesJsonSchema\w*\s*\(\s*['\"]?([^'\"()]{1,80})"),
    re.compile(r"\.json\(\)\s*\[\s*['\"]([^'\"]{1,60})['\"]\s*\]"),
)
_AUTH_PATTERNS = (
    re.compile(r"(?i)\b(bearer|oauth2?|basicAuth|withUser|jwt|api[_-]?key)\b"),
)


class ApiCoverageService:
    """Prove that existing API test coverage survives generated file writes.

    A coverage graph (endpoints exercised, statuses and body shapes asserted,
    auth signals) is captured for every file the generator is about to touch,
    then recaptured after the write; lost signals are reported instead of
    silently accepted when a file is updated in place.
    """

    def snapshot_files(self, repo_path: str, relative_paths: list[str]) -> list[ApiCoverageEntry]:
        root = Path(repo_path)
        entries: list[ApiCoverageEntry] = []
        for relative in sorted(set(relative_paths)):
            target = root / relative
            if not target.is_file():
                continue
            entries.append(
                self.entry_from_source(
                    relative, target.read_text(encoding="utf-8", errors="ignore")
                )
            )
        return entries

    def entry_from_source(self, file_path: str, source: str) -> ApiCoverageEntry:
        endpoints = sorted(
            {match for pattern in _ENDPOINT_PATTERNS for match in pattern.findall(source)}
        )
        statuses = sorted(
            {str(match) for pattern in _STATUS_PATTERNS for match in pattern.findall(source)}
        )
        bodies = sorted(
            {match for pattern in _BODY_PATTERNS for match in pattern.findall(source)}
        )
        auth = sorted(
            {match.lower() for pattern in _AUTH_PATTERNS for match in pattern.findall(source)}
        )
        return ApiCoverageEntry(
            file_path=file_path,
            endpoints=endpoints,
            status_assertions=statuses,
            body_assertions=bodies,
            auth_signals=auth,
        )

    def compare(
        self,
        before: list[ApiCoverageEntry],
        after: list[ApiCoverageEntry],
    ) -> ApiCoverageReport:
        before_map = {entry.file_path: entry for entry in before}
        after_map = {entry.file_path: entry for entry in after}

        removed = [entry for path, entry in before_map.items() if path not in after_map]
        added = [entry for path, entry in after_map.items() if path not in before_map]
        preserved: list[ApiCoverageEntry] = []
        modified: list[ApiCoverageModification] = []
        for path, entry in before_map.items():
            counterpart = after_map.get(path)
            if counterpart is None:
                continue
            lost = sorted(entry.signals() - counterpart.signals())
            gained = sorted(counterpart.signals() - entry.signals())
            if lost or gained:
                modified.append(
                    ApiCoverageModification(
                        file_path=path, lost_signals=lost, gained_signals=gained
                    )
                )
            else:
                preserved.append(counterpart)

        lost_coverage = bool(removed) or any(item.lost_signals for item in modified)
        report = ApiCoverageReport(
            preserved=preserved,
            added=added,
            removed=removed,
            modified=modified,
            coverage_preserved=not lost_coverage,
            summary=[
                *(f"Preserved: {entry.file_path}" for entry in preserved),
                *(f"Added: {entry.file_path}" for entry in added),
                *(f"Removed: {entry.file_path}" for entry in removed),
                *(
                    f"Modified: {item.file_path} "
                    f"(lost {len(item.lost_signals)}, gained {len(item.gained_signals)})"
                    for item in modified
                ),
            ],
        )
        logger.log(
            logging.WARNING if lost_coverage else logging.INFO,
            "API coverage %s (preserved=%s added=%s removed=%s modified=%s)",
            "LOST" if lost_coverage else "preserved",
            len(preserved),
            len(added),
            len(removed),
            len(modified),
        )
        return report

    def review_reasons(self, report: ApiCoverageReport) -> list[str]:
        reasons = [
            f"Coverage lost: existing API test file {entry.file_path} no longer "
            "exists after generation."
            for entry in report.removed
        ]
        reasons.extend(
            f"Coverage weakened: {item.file_path} lost API signals {item.lost_signals}."
            for item in report.modified
            if item.lost_signals
        )
        return reasons
