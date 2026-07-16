from __future__ import annotations

import re
from typing import Any

from worktop.core_services.app.utility.custom_logger.logging import logger


class TsAstParserTool:
    """Small structural TypeScript parser used for safe patch placement.

    It deliberately exposes source offsets, not line guesses. Full compiler
    validation can still run afterward when a repository provides `tsc`.
    """

    def parse(self, file_path: str, content: str) -> dict[str, Any]:
        logger.info("[playwright-generation] stage=ts_ast_parse status=started path=%s", file_path)
        self.validate_structure(content)
        result = {
            "file_path": file_path,
            "exports": re.findall(r"\bexport\s+(?:default\s+)?(?:class|const|function|interface|type)\s+(\w+)", content),
            "imports": re.findall(r"^\s*import\b[^;]*;?", content, re.MULTILINE),
            "classes": self._named_blocks(content, r"\bclass\s+(?P<name>\w+)[^{]*\{"),
            "objects": self._named_blocks(content, r"\b(?:const|let|var)\s+(?P<name>\w+)\s*=\s*\{"),
        }
        logger.info("[playwright-generation] stage=ts_ast_parse status=completed path=%s", file_path)
        return result

    def find_class(self, content: str, name: str) -> dict[str, int] | None:
        return self._find_named_block(content, rf"\bclass\s+{re.escape(name)}\b[^{{]*\{{")

    def find_object(self, content: str, name: str) -> dict[str, int] | None:
        return self._find_named_block(
            content, rf"\b(?:const|let|var)\s+{re.escape(name)}\s*=\s*\{{"
        )

    def validate_structure(self, content: str) -> None:
        stack: list[str] = []
        pairs = {"}": "{", ")": "(", "]": "["}
        quote: str | None = None
        escaped = False
        line_comment = False
        block_comment = False
        index = 0
        while index < len(content):
            char = content[index]
            nxt = content[index + 1] if index + 1 < len(content) else ""
            if line_comment:
                if char == "\n": line_comment = False
            elif block_comment:
                if char == "*" and nxt == "/": block_comment = False; index += 1
            elif quote:
                if escaped: escaped = False
                elif char == "\\": escaped = True
                elif char == quote: quote = None
            elif char == "/" and nxt == "/": line_comment = True; index += 1
            elif char == "/" and nxt == "*": block_comment = True; index += 1
            elif char in {"'", '"', "`"}: quote = char
            elif char in "{([": stack.append(char)
            elif char in "})]":
                if not stack or stack.pop() != pairs[char]:
                    raise ValueError(f"Unbalanced TypeScript delimiter `{char}`")
            index += 1
        if stack or quote or block_comment:
            raise ValueError("Unbalanced TypeScript structure")

    def _named_blocks(self, content: str, pattern: str) -> list[dict[str, Any]]:
        blocks = []
        for match in re.finditer(pattern, content):
            block = self._block_from_match(content, match)
            blocks.append({"name": match.group("name"), **block})
        return blocks

    def _find_named_block(self, content: str, pattern: str) -> dict[str, int] | None:
        match = re.search(pattern, content)
        return self._block_from_match(content, match) if match else None

    def _block_from_match(self, content: str, match: re.Match[str]) -> dict[str, int]:
        open_offset = content.find("{", match.start(), match.end())
        close_offset = self._matching_brace(content, open_offset)
        return {"start": match.start(), "body_start": open_offset + 1, "body_end": close_offset, "end": close_offset + 1}

    def _matching_brace(self, content: str, start: int) -> int:
        depth = 0
        quote: str | None = None
        escaped = False
        for index in range(start, len(content)):
            char = content[index]
            if quote:
                if escaped: escaped = False
                elif char == "\\": escaped = True
                elif char == quote: quote = None
                continue
            if char in {"'", '"', "`"}: quote = char
            elif char == "{": depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0: return index
        raise ValueError("Unclosed TypeScript block")
