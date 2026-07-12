from __future__ import annotations

from pathlib import Path


from worktop.test_agent.app.patching.diff_generator import DiffGenerator
from worktop.test_agent.app.patching.patch_planner import PatchPlanner
from worktop.test_agent.app.schemas.code_patch import AppliedPatch, PatchSet, PatchWriteResult
from worktop.test_agent.app.tools.playwright_parser_tool import PlaywrightParserTool
from worktop.core_services.app.utility.custom_logger.logging import logger



class ScopedPatchWriter:
    def __init__(self) -> None:
        self.diffs = DiffGenerator()
        self.planner = PatchPlanner()
        self.playwright_parser = PlaywrightParserTool()

    def apply(self, repo_path: str, patches: PatchSet) -> PatchWriteResult:
        logger.info(
            "[playwright-generation] stage=patch_writer status=started "
            f"repo={repo_path} requested_patches={len(patches.patches)}"
        )
        try:
            planned = self.planner.validate(patches)
            logger.info(
                "[playwright-generation] stage=patch_writer status=validated "
                f"planned_patches={len(planned.patches)}"
            )
            result = PatchWriteResult()
            for patch in planned.patches:
                logger.info(
                    "[playwright-generation] stage=patch_writer status=applying "
                    f"operation={patch.operation} path={patch.path}"
                )
                path = self._resolve_safe_path(repo_path, patch.path)
                path.parent.mkdir(parents=True, exist_ok=True)
                existed_before = path.exists()
                before = path.read_text(encoding="utf-8") if existed_before else ""
                after = self._apply_content(before, patch)
                path.write_text(after, encoding="utf-8")
                result.applied.append(
                    AppliedPatch(
                        path=patch.path,
                        operation=patch.operation,
                        diff=self.diffs.unified(before, after, patch.path),
                        original_content=before if existed_before else None,
                    )
                )
            logger.info(
                "[playwright-generation] stage=patch_writer status=completed "
                f"applied={len(result.applied)}"
            )
            return result
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=patch_writer status=failed "
                f"error={exc}"
            )
            raise

    def rollback(self, repo_path: str, result: PatchWriteResult) -> None:
        logger.info(
            "[playwright-generation] stage=patch_writer_rollback status=started repo=%s patches=%s",
            repo_path,
            len(result.applied),
        )
        for applied in reversed(result.applied):
            path = self._resolve_safe_path(repo_path, applied.path)
            if applied.original_content is not None:
                path.write_text(applied.original_content, encoding="utf-8")
                logger.info(
                    "[playwright-generation] stage=patch_writer_rollback status=restored path=%s",
                    applied.path,
                )
            elif applied.operation == "create" and path.exists():
                path.unlink()
                logger.info(
                    "[playwright-generation] stage=patch_writer_rollback status=removed_created_file path=%s",
                    applied.path,
                )
            else:
                logger.warning(
                    "[playwright-generation] stage=patch_writer_rollback status=skipped path=%s",
                    applied.path,
                )
        logger.info("[playwright-generation] stage=patch_writer_rollback status=completed")

    def _resolve_safe_path(self, repo_path: str, relative_path: str) -> Path:
        root = Path(repo_path).resolve()
        path = (root / relative_path).resolve()
        if root != path and root not in path.parents:
            raise ValueError(f"Patch path escapes repository root: {relative_path}")
        return path

    def _apply_content(self, before: str, patch) -> str:
        content = patch.content
        if content and not content.endswith("\n"):
            content = f"{content}\n"

        if patch.operation == "create":
            if before:
                raise ValueError(f"Create patch target already exists: {patch.path}")
            return content

        lines = before.splitlines(keepends=True)
        if patch.operation == "replace":
            start = (patch.start_line or 1) - 1
            end = patch.end_line or patch.start_line or 1
            if start < 0 or end > len(lines):
                raise ValueError(f"Replace patch range is outside file: {patch.path}")
            return "".join(lines[:start] + [content] + lines[end:])

        if patch.operation == "append":
            existing_tests = self.playwright_parser.extract_tests(patch.path, before)
            generated_tests = self.playwright_parser.extract_tests(patch.path, content)
            if len(generated_tests) != 1:
                raise ValueError(
                    f"Append patch must contain exactly one complete test block: {patch.path}"
                )
            existing_titles = {test.test_title for test in existing_tests}
            duplicates = sorted(
                test.test_title for test in generated_tests if test.test_title in existing_titles
            )
            if duplicates:
                raise ValueError(
                    f"Generated test title already exists in {patch.path}: {', '.join(duplicates)}"
                )

            describes = self.playwright_parser.extract_describes(patch.path, before)
            if patch.start_line is None:
                if len(describes) != 1:
                    raise ValueError(
                        f"Append patch requires start_line when {patch.path} does not contain exactly one describe block"
                    )
                insertion_index = describes[0].end_line - 1
            else:
                containing = [
                    block
                    for block in describes
                    if block.start_line < patch.start_line <= block.end_line
                ]
                if not containing:
                    raise ValueError(
                        f"Append start_line must be inside a describe block: {patch.path}"
                    )
                insertion_index = max(containing, key=lambda block: block.start_line).end_line - 1
            return "".join(lines[:insertion_index] + [content] + lines[insertion_index:])

        raise ValueError(f"Unsupported patch operation: {patch.operation}")
