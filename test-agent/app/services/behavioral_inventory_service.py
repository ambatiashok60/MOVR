from __future__ import annotations

import logging
from pathlib import Path


from app.schemas.behavioral_test_unit import BehavioralTestUnit
from app.schemas.repository_inventory import RepositoryInventory
from app.tools.playwright_parser_tool import PlaywrightParserTool

logger = logging.getLogger(__name__)


class BehavioralInventoryService:
    def __init__(self) -> None:
        self.parser = PlaywrightParserTool()

    def extract(self, inventory: RepositoryInventory) -> list[BehavioralTestUnit]:
        logger.info(
            "[playwright-generation] stage=behavioral_inventory status=started repo_head=%s",
            inventory.repo_head,
        )
        try:
            units: list[BehavioralTestUnit] = []
            root = Path(inventory.repo_path)
            for test_file in inventory.test_files:
                if not test_file.is_e2e_candidate:
                    logger.debug(
                        "[playwright-generation] stage=behavioral_inventory "
                        "status=skipped_non_e2e path=%s kind=%s",
                        test_file.path,
                        test_file.kind,
                    )
                    continue
                path = root / test_file.path
                if not path.exists():
                    logger.debug(
                        "[playwright-generation] stage=behavioral_inventory "
                        "status=skipped_missing path=%s",
                        test_file.path,
                    )
                    continue
                content = path.read_text(encoding="utf-8", errors="ignore")
                extracted = self.parser.extract_tests(test_file.path, content)
                validated = self._filter_integrity(test_file.path, content, extracted)
                logger.debug(
                    "[playwright-generation] stage=behavioral_inventory "
                    "status=parsed_spec path=%s tests=%s valid_tests=%s rejected_tests=%s",
                    test_file.path,
                    len(extracted),
                    len(validated),
                    len(extracted) - len(validated),
                )
                units.extend(validated)
            logger.info(
                "[playwright-generation] stage=behavioral_inventory status=completed units=%s",
                len(units),
            )
            return units
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=behavioral_inventory status=failed error=%s",
                exc,
            )
            raise

    def _filter_integrity(
        self,
        file_path: str,
        content: str,
        units: list[BehavioralTestUnit],
    ) -> list[BehavioralTestUnit]:
        validated: list[BehavioralTestUnit] = []
        for unit in units:
            findings = self._integrity_findings(content, unit)
            if findings:
                logger.warning(
                    "[playwright-generation] stage=behavioral_inventory "
                    "status=rejected_parser_candidate path=%s title=%s lines=%s-%s reasons=%s",
                    file_path,
                    unit.test_title,
                    unit.start_line,
                    unit.end_line,
                    findings,
                )
                continue
            logger.debug(
                "[playwright-generation] stage=behavioral_inventory "
                "status=accepted_parser_candidate path=%s title=%s lines=%s-%s",
                file_path,
                unit.test_title,
                unit.start_line,
                unit.end_line,
            )
            validated.append(unit)
        return validated

    def _integrity_findings(
        self,
        content: str,
        unit: BehavioralTestUnit,
    ) -> list[str]:
        findings: list[str] = []
        lines = content.splitlines()
        if unit.start_line < 1:
            findings.append("start_line_before_file")
        if unit.end_line < unit.start_line:
            findings.append("end_line_before_start_line")
        if unit.end_line > len(lines):
            findings.append("end_line_after_file")
        if findings:
            return findings

        source_range = "\n".join(lines[unit.start_line - 1 : unit.end_line]).strip()
        if not source_range:
            findings.append("empty_source_range")
            return findings
        if unit.test_title not in source_range:
            findings.append("title_missing_from_source_range")
        if not unit.source_excerpt:
            findings.append("empty_source_excerpt")
        elif unit.source_excerpt.strip() not in source_range:
            findings.append("source_excerpt_not_in_source_range")
        if not self.parser.TEST_PATTERN.search(source_range):
            findings.append("test_declaration_missing_from_source_range")
        if "=>" not in source_range and "function" not in source_range:
            findings.append("callback_marker_missing_from_source_range")
        if not self._has_balanced_braces(source_range):
            findings.append("unbalanced_braces_in_source_range")
        return findings

    def _has_balanced_braces(self, source: str) -> bool:
        depth = 0
        quote: str | None = None
        escaped = False
        in_line_comment = False
        in_block_comment = False
        for index, char in enumerate(source):
            next_char = source[index + 1] if index + 1 < len(source) else ""
            if in_line_comment:
                if char == "\n":
                    in_line_comment = False
                continue
            if in_block_comment:
                if char == "*" and next_char == "/":
                    in_block_comment = False
                continue
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                continue
            if char == "/" and next_char == "/":
                in_line_comment = True
                continue
            if char == "/" and next_char == "*":
                in_block_comment = True
                continue
            if char in {"'", '"', "`"}:
                quote = char
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth < 0:
                    return False
        return depth == 0 and not quote and not in_block_comment
