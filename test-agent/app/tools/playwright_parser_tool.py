from __future__ import annotations

import logging
import re


from app.schemas.behavioral_test_unit import BehavioralTestUnit, PlaywrightDescribeBlock

logger = logging.getLogger(__name__)


class PlaywrightParserTool:
    MAX_SOURCE_EXCERPT_CHARS = 6000
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

    def extract_tests(self, file_path: str, content: str) -> list[BehavioralTestUnit]:
        logger.info(
            "[playwright-generation] stage=playwright_parse status=started path=%s",
            file_path,
        )
        try:
            describes = self.extract_describes(file_path, content)
            units = []
            for match in self.TEST_PATTERN.finditer(content):
                if self._is_inside_non_code(content, match.start()):
                    logger.debug(
                        "[playwright-generation] stage=playwright_parse "
                        "status=skipped_non_code_match path=%s line=%s title=%s",
                        file_path,
                        self._line_number(content, match.start()),
                        self._clean_title(match.group("title")),
                    )
                    continue
                end_offset = self._find_call_end_offset(content, match.end())
                if end_offset <= match.end():
                    logger.warning(
                        "[playwright-generation] stage=playwright_parse "
                        "status=skipped_invalid_body path=%s line=%s title=%s",
                        file_path,
                        self._line_number(content, match.start()),
                        self._clean_title(match.group("title")),
                    )
                    continue
                start_line = self._line_number(content, match.start())
                end_line = self._line_number(content, end_offset)
                describe_title = self._find_containing_describe(
                    describes=describes,
                    start_line=start_line,
                    end_line=end_line,
                )
                block = content[match.start() : max(end_offset, match.end())]
                units.append(
                    BehavioralTestUnit(
                        file_path=file_path,
                        describe_title=describe_title,
                        test_title=self._clean_title(match.group("title")),
                        start_line=start_line,
                        end_line=end_line,
                        fixtures=self._extract_fixtures(block),
                        page_objects=self._extract_page_objects(block),
                        behavior_summary=self._summarize_behavior(block),
                        source_excerpt=self._trim_source_excerpt(block),
                    )
                )
            logger.info(
                "[playwright-generation] stage=playwright_parse status=completed path=%s tests=%s",
                file_path,
                len(units),
            )
            return units
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=playwright_parse status=failed path=%s error=%s",
                file_path,
                exc,
            )
            raise

    def extract_describes(
        self,
        file_path: str,
        content: str,
    ) -> list[PlaywrightDescribeBlock]:
        logger.info(
            "[playwright-generation] stage=playwright_describe_parse status=started path=%s",
            file_path,
        )
        try:
            blocks = []
            for match in self.DESCRIBE_PATTERN.finditer(content):
                if self._is_inside_non_code(content, match.start()):
                    logger.debug(
                        "[playwright-generation] stage=playwright_describe_parse "
                        "status=skipped_non_code_match path=%s line=%s title=%s",
                        file_path,
                        self._line_number(content, match.start()),
                        self._clean_title(match.group("title")),
                    )
                    continue
                end_offset = self._find_call_end_offset(content, match.end())
                if end_offset <= match.end():
                    logger.warning(
                        "[playwright-generation] stage=playwright_describe_parse "
                        "status=skipped_invalid_body path=%s line=%s title=%s",
                        file_path,
                        self._line_number(content, match.start()),
                        self._clean_title(match.group("title")),
                    )
                    continue
                blocks.append(
                    PlaywrightDescribeBlock(
                        file_path=file_path,
                        title=self._clean_title(match.group("title")),
                        start_line=self._line_number(content, match.start()),
                        end_line=self._line_number(content, end_offset),
                    )
                )
            logger.info(
                "[playwright-generation] stage=playwright_describe_parse status=completed path=%s describes=%s",
                file_path,
                len(blocks),
            )
            return blocks
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=playwright_describe_parse status=failed path=%s error=%s",
                file_path,
                exc,
            )
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
        brace_offset = self._find_callback_body_offset(content, search_from)
        if brace_offset == -1:
            return search_from
        return self._find_matching_brace(content, brace_offset)

    def _find_callback_body_offset(self, content: str, search_from: int) -> int:
        paren_depth = 1
        bracket_depth = 0
        quote: str | None = None
        escaped = False
        in_line_comment = False
        in_block_comment = False
        callback_marker_seen = False
        index = search_from

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
            if char == "=" and next_char == ">" and paren_depth == 1:
                callback_marker_seen = True
                index += 2
                continue
            if self._is_word_at(content, index, "function") and paren_depth == 1:
                callback_marker_seen = True
                index += len("function")
                continue
            if char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth -= 1
                if paren_depth <= 0:
                    return -1
            elif char == "[":
                bracket_depth += 1
            elif char == "]":
                bracket_depth = max(bracket_depth - 1, 0)
            elif char == "{" and paren_depth == 1 and bracket_depth == 0:
                if callback_marker_seen:
                    return index
            index += 1

        return -1

    def _is_word_at(self, content: str, index: int, word: str) -> bool:
        if not content.startswith(word, index):
            return False
        before = content[index - 1] if index > 0 else ""
        after_index = index + len(word)
        after = content[after_index] if after_index < len(content) else ""
        return not (before.isalnum() or before == "_") and not (
            after.isalnum() or after == "_"
        )

    def _is_inside_non_code(self, content: str, target_offset: int) -> bool:
        quote: str | None = None
        escaped = False
        in_line_comment = False
        in_block_comment = False
        index = 0

        while index < min(target_offset, len(content)):
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

        return bool(quote or in_line_comment or in_block_comment)

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

    def _extract_fixtures(self, block: str) -> list[str]:
        fixtures: set[str] = set()
        fixture_match = re.search(r"async\s*\(\s*\{(?P<fixtures>[^}]+)\}", block)
        if fixture_match:
            fixtures.update(
                item.strip().split(":")[0].strip()
                for item in fixture_match.group("fixtures").split(",")
                if item.strip()
            )
        if "storageState" in block:
            fixtures.add("storageState")
        if "test.use" in block:
            fixtures.add("test.use")
        return sorted(fixtures)

    def _extract_page_objects(self, block: str) -> list[str]:
        page_objects = {
            match.group("name")
            for match in re.finditer(r"\bnew\s+(?P<name>[A-Z][A-Za-z0-9]*Page)\b", block)
        }
        return sorted(page_objects)

    def _summarize_behavior(self, block: str) -> str:
        actions: list[str] = []
        for token, label in (
            (".goto(", "navigates"),
            (".click(", "clicks"),
            (".fill(", "fills input"),
            (".selectOption(", "selects option"),
            ("page.route", "stubs network"),
            ("route.fulfill", "fulfills network response"),
            ("expect(", "asserts outcome"),
        ):
            if token in block:
                actions.append(label)
        return ", ".join(actions)

    def _trim_source_excerpt(self, block: str) -> str:
        excerpt = block.strip()
        if len(excerpt) <= self.MAX_SOURCE_EXCERPT_CHARS:
            return excerpt
        return f"{excerpt[: self.MAX_SOURCE_EXCERPT_CHARS].rstrip()}\n// ... truncated"
