"""Placement of generated tests into existing test files (test_agent parity).

The placement agent proposes merging generated tests into an existing test
file; this service is the deterministic safety floor around that proposal.
A merge is accepted only when it provably preserves what is already there —
every coverage signal (endpoints, statuses, body shapes, auth) and every
detected test name from the original file must survive verbatim in the merged
content. Anything unprovable falls back to create_new, which is always safe
because the write guard already vets new-file paths.
"""

from __future__ import annotations

import re

from worktop.api_agent.app.agents.test_placement_agent import TestPlacementAgent
from worktop.api_agent.app.coverage.api_coverage_service import ApiCoverageService
from worktop.api_agent.app.schemas.llm_outputs import GeneratedTestFileOutput, TestCodeOutput
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.source_context import GenerationSourceContext
from worktop.api_agent.app.schemas.test_placement import TestPlacementDecision
from worktop.api_agent.app.tools.path_safety import resolve_workspace_path, safe_join
from worktop.api_agent.app.utils.logging_utils import log_exception, log_step

_TEST_NAME_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (".py", re.compile(r"def\s+(test_\w+)")),
    (".java", re.compile(r"@Test[\s\S]{0,200}?(?:void|fun)\s+(\w+)\s*\(")),
    (".kt", re.compile(r"@Test[\s\S]{0,200}?(?:void|fun)\s+(\w+)\s*\(")),
    (".ts", re.compile(r"(?:\bit|\btest)\s*\(\s*['\"]([^'\"]+)['\"]")),
    (".js", re.compile(r"(?:\bit|\btest)\s*\(\s*['\"]([^'\"]+)['\"]")),
)


class TestPlacementService:
    __test__ = False  # prevent pytest collection

    def __init__(
        self,
        agent: TestPlacementAgent,
        coverage: ApiCoverageService | None = None,
    ) -> None:
        self.agent = agent
        self.coverage = coverage or ApiCoverageService()

    def apply(
        self,
        repo_path: str,
        output: TestCodeOutput,
        profile: RepoProfile,
        source_context: GenerationSourceContext | None = None,
        repo_understanding=None,
    ) -> tuple[TestCodeOutput, list[str], list[str]]:
        """Rewrite ``output.files`` per verified placement decisions.

        Returns (output, warnings, review_reasons); the output is unchanged
        whenever placement fails or nothing can be safely merged.
        """
        warnings: list[str] = []
        review_reasons: list[str] = []
        if not output.files or not profile.existing_tests:
            return output, warnings, review_reasons

        try:
            placement = self.agent.place(
                output,
                profile,
                repo_path,
                source_context=source_context,
                repo_understanding=repo_understanding,
            )
        except Exception as exc:
            log_exception(exc, context={"stage": "test_placement", "repo_path": repo_path})
            warnings.append(
                "Test placement agent failed; all generated tests were kept as "
                "new files."
            )
            return output, warnings, review_reasons

        decisions = {
            decision.generated_path: decision for decision in placement.decisions
        }
        root = resolve_workspace_path(repo_path)
        merged_files: list[GeneratedTestFileOutput] = []
        extended = 0
        for file in output.files:
            decision = decisions.get(file.relative_path)
            if decision is None or decision.action != "extend_existing":
                merged_files.append(file)
                continue
            findings = self._verify_extension(root, decision)
            if findings:
                message = (
                    f"Placement of `{file.relative_path}` into "
                    f"`{decision.target_existing_path}` was rejected: "
                    + "; ".join(findings)
                    + ". The tests were kept as a new file."
                )
                warnings.append(message)
                review_reasons.append(message)
                merged_files.append(file)
                continue
            merged_files.append(
                file.model_copy(
                    update={
                        "relative_path": decision.target_existing_path,
                        "content": decision.merged_content,
                        "summary": (
                            f"Extended existing test file with: {file.summary}"
                        ),
                    }
                )
            )
            extended += 1
            warnings.append(
                f"Generated tests for `{file.relative_path}` were merged into "
                f"existing `{decision.target_existing_path}` "
                "(existing coverage verified preserved)."
            )

        log_step(
            "test_placement_completed",
            {
                "input_files": len(output.files),
                "extended_existing": extended,
                "created_new": len(output.files) - extended,
                "agent_warnings": placement.warnings[:5],
            },
        )
        warnings.extend(placement.warnings)
        return output.model_copy(update={"files": merged_files}), warnings, review_reasons

    def _verify_extension(self, root, decision: TestPlacementDecision) -> list[str]:
        findings: list[str] = []
        target = (decision.target_existing_path or "").strip()
        merged = decision.merged_content or ""
        if not target:
            return ["no target_existing_path was provided"]
        if not merged.strip():
            return ["no merged_content was provided"]
        try:
            target_file = safe_join(root, target)
        except Exception:
            return ["target path escapes the repository root"]
        if not target_file.is_file():
            return ["target file does not exist"]

        original = target_file.read_text(encoding="utf-8", errors="ignore")
        if len(merged) <= len(original):
            findings.append(
                "merged content is not larger than the original file, so the "
                "new tests cannot all be additions"
            )

        lost_signals = sorted(
            self.coverage.entry_from_source(target, original).signals()
            - self.coverage.entry_from_source(target, merged).signals()
        )
        if lost_signals:
            findings.append(f"merged content loses coverage signals {lost_signals}")

        missing_names = self._test_names(target, original) - self._test_names(
            target, merged
        )
        if missing_names:
            findings.append(
                f"merged content drops existing tests {sorted(missing_names)}"
            )
        return findings

    def _test_names(self, path: str, content: str) -> set[str]:
        for suffix, pattern in _TEST_NAME_PATTERNS:
            if path.endswith(suffix):
                return set(pattern.findall(content))
        return set()
