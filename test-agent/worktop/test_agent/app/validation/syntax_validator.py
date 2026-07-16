from __future__ import annotations

from pathlib import Path

from worktop.test_agent.app.schemas.code_patch import PatchSet
from worktop.test_agent.app.schemas.validation_result import ValidationCheck
from worktop.test_agent.app.tools.ts_ast_parser_tool import TsAstParserTool


class SyntaxValidator:
    def __init__(self) -> None:
        self.parser = TsAstParserTool()

    def validate(self, repo_path: str, patches: PatchSet | None = None) -> ValidationCheck:
        findings: list[str] = []
        root = Path(repo_path).resolve()
        for patch in patches.patches if patches else []:
            if not patch.path.endswith((".ts", ".tsx", ".js", ".jsx")):
                continue
            path = (root / patch.path).resolve()
            if root != path and root not in path.parents:
                findings.append(f"Unsafe changed-file path: {patch.path}")
                continue
            if not path.is_file():
                findings.append(f"Changed source file does not exist: {patch.path}")
                continue
            try:
                self.parser.parse(
                    patch.path, path.read_text(encoding="utf-8", errors="ignore")
                )
            except ValueError as exc:
                findings.append(f"{patch.path}: {exc}")
        return ValidationCheck(
            name="syntax",
            passed=not findings,
            output="\n".join(findings) if findings else "Changed source files are structurally balanced.",
        )
