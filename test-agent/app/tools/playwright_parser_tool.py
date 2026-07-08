from __future__ import annotations

import re
from typing import Any

from worktop.core_services.app.utility.custom_logger.log_helpers import (
    log_card_simple,
    log_exception,
    log_metric,
    log_step,
)
from worktop.core_services.app.utility.custom_logger.logging import (
    log_performance,
    logger,
)

from app.schemas.behavioral_test_unit import BehavioralTestUnit, PlaywrightDescribeBlock


class PlaywrightParserTool:
    DESCRIBE_PATTERN = re.compile(
        r"(?:\btest\.)?\bdescribe(?:\.(?:only|skip|fixme|serial|parallel))?"
        r"\s*\(\s*(['\"])(?P<title>.*?)\1",
        re.DOTALL,
    )
    TEST_PATTERN = re.compile(
        r"(?<!\.)\btest(?:\.(?:only|skip|fixme|slow))?"
        r"\s*\(\s*(['\"])(?P<title>.*?)\1",
        re.DOTALL,
    )

    @log_performance("playwright_parser_tool.extract_tests")
    def extract_tests(self, file_path: str, content: str) -> list[BehavioralTestUnit]:
        log_step("playwright_parse_started", {"stage": "playwright_parse"})
        try:
            describes = self.extract_describes(file_path, content)
            units = []
            for match in self.TEST_PATTERN.finditer(content):
                end_offset = self._find_call_end_offset(content, match.end())
                start_line = self._line_number(content, match.start())
                end_line = self._line_number(content, end_offset)
                describe_title = self._find_containing_describe(
                    describes=describes,
                    start_line=start_line,
                    end_line=end_line,
                )
                units.append(
                    BehavioralTestUnit(
                        file_path=file_path,
                        describe_title=describe_title,
                        test_title=self._clean_title(match.group("title")),
                        start_line=start_line,
                        end_line=end_line,
                    )
                )
            log_metric("playwright_test_count", len(units))
            return units
        except Exception as exc:
            log_exception(exc, context={"stage": "playwright_parse"})
            raise

    @log_performance("playwright_parser_tool.extract_describes")
    def extract_describes(
        self,
        file_path: str,
        content: str,
    ) -> list[PlaywrightDescribeBlock]:
        log_step("playwright_describe_parse_started", {"stage": "playwright_parse"})
        try:
            blocks = []
            for match in self.DESCRIBE_PATTERN.finditer(content):
                end_offset = self._find_call_end_offset(content, match.end())
                blocks.append(
                    PlaywrightDescribeBlock(
                        file_path=file_path,
                        title=self._clean_title(match.group("title")),
                        start_line=self._line_number(content, match.start()),
                        end_line=self._line_number(content, end_offset),
                    )
                )
            log_metric("playwright_describe_count", len(blocks))
            return blocks
        except Exception as exc:
            log_exception(exc, context={"stage": "playwright_parse"})
            raise

    def _find_containing_describe(
        self,
        describes: list[PlaywrightDescribeBlock],
        start_line: int,
        end_line: int,
    ) -> str | None:
        containing = [
            block
            for block in describes
            if block.start_line <= start_line and block.end_line >= end_line
        ]
        if not containing:
            return None
        return max(containing, key=lambda block: block.start_line).title

    def _find_call_end_offset(self, content: str, search_from: int) -> int:
        brace_offset = content.find("{", search_from)
        if brace_offset == -1:
            return search_from
        return self._find_matching_brace(content, brace_offset)

    def _find_matching_brace(self, content: str, open_offset: int) -> int:
        depth = 0
        quote: str | None = None
        escaped = False
        in_line_comment = False
        in_block_comment = False
        index = open_offset

        while index < len(content):
            char = content[index]
            next_char = content[index + 1] if index + 1 < len(content) else ""

            if in_line_comment:
                if char == "\n":
                    in_line_comment = False
                index += 1
                continue

            if in_block_comment:
                if char == "*" and next_char == "/":
                    in_block_comment = False
                    index += 2
                    continue
                index += 1
                continue

            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                index += 1
                continue

            if char == "/" and next_char == "/":
                in_line_comment = True
                index += 2
                continue
            if char == "/" and next_char == "*":
                in_block_comment = True
                index += 2
                continue
            if char in {"'", '"', "`"}:
                quote = char
                index += 1
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    semicolon_offset = content.find(";", index)
                    if semicolon_offset != -1 and "\n" not in content[index:semicolon_offset]:
                        return semicolon_offset
                    return index
            index += 1

        return open_offset

    def _line_number(self, content: str, offset: int) -> int:
        return content[: max(offset, 0)].count("\n") + 1

    def _clean_title(self, title: str) -> str:
        return " ".join(title.split())
