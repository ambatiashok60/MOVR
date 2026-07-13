from __future__ import annotations

from pathlib import Path
import re


from worktop.test_agent.app.patching.diff_generator import DiffGenerator
from worktop.test_agent.app.patching.patch_planner import PatchPlanner
from worktop.test_agent.app.schemas.code_patch import AppliedPatch, PatchSet, PatchWriteResult
from worktop.test_agent.app.tools.playwright_parser_tool import PlaywrightParserTool
from worktop.test_agent.app.tools.ts_ast_parser_tool import TsAstParserTool
from worktop.core_services.app.utility.custom_logger.logging import logger



class ScopedPatchWriter:
    def __init__(self) -> None:
        self.diffs = DiffGenerator()
        self.planner = PatchPlanner()
        self.playwright_parser = PlaywrightParserTool()
        self.ts_parser = TsAstParserTool()

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
            proposed: dict[Path, str] = {}
            for patch in planned.patches:
                logger.info(
                    "[playwright-generation] stage=patch_writer status=applying "
                    f"operation={patch.operation} path={patch.path}"
                )
                path = self._resolve_safe_path(repo_path, patch.path)
                existed_before = path.exists()
                before = proposed.get(
                    path,
                    path.read_text(encoding="utf-8") if existed_before else "",
                )
                after = self._apply_content(before, patch)
                if patch.path.endswith((".ts", ".tsx", ".js", ".jsx")):
                    self.ts_parser.parse(patch.path, after)
                proposed[path] = after
                result.applied.append(
                    AppliedPatch(
                        path=patch.path,
                        operation=patch.operation,
                        diff=self.diffs.unified(before, after, patch.path),
                        original_content=before if existed_before else None,
                    )
                )
            for path, content in proposed.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
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

        if patch.operation == "insert_class_member":
            block = self.ts_parser.find_class(before, patch.target_symbol or "")
            if block is None:
                raise ValueError(
                    f"Class `{patch.target_symbol}` not found in {patch.path}"
                )
            class_body = before[block["body_start"] : block["body_end"]]
            if patch.member_name and self._member_exists(class_body, patch.member_name):
                raise ValueError(
                    f"Class member `{patch.member_name}` already exists in {patch.path}"
                )
            return self._insert_before_block_end(before, block["body_end"], content)

        if patch.operation == "insert_object_property":
            block = self.ts_parser.find_object(before, patch.target_symbol or "")
            if block is None:
                raise ValueError(
                    f"Object `{patch.target_symbol}` not found in {patch.path}"
                )
            object_body = before[block["body_start"] : block["body_end"]]
            if patch.member_name and self._member_exists(object_body, patch.member_name):
                raise ValueError(
                    f"Object property `{patch.member_name}` already exists in {patch.path}"
                )
            return self._insert_before_block_end(before, block["body_end"], content)

        if patch.operation == "insert_import":
            if patch.content.strip() in before:
                return before
            imports = list(self.ts_parser.parse(patch.path, before)["imports"])
            if not imports:
                return f"{content}{before}"
            last_import = imports[-1]
            offset = before.rfind(last_import) + len(last_import)
            return f"{before[:offset]}\n{content.rstrip()}{before[offset:]}"

        raise ValueError(f"Unsupported patch operation: {patch.operation}")

    def _member_exists(self, body: str, name: str) -> bool:
        return bool(re.search(rf"\b{re.escape(name)}\s*[:=(]", body))

    def _insert_before_block_end(self, before: str, offset: int, content: str) -> str:
        prefix = before[:offset].rstrip()
        suffix = before[offset:]
        return f"{prefix}\n{content.rstrip()}\n{suffix}"
