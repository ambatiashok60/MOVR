from __future__ import annotations

from pathlib import Path

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

from app.patching.backup_manager import BackupManager
from app.patching.diff_generator import DiffGenerator
from app.patching.patch_planner import PatchPlanner
from app.schemas.code_patch import AppliedPatch, PatchSet, PatchWriteResult


class ScopedPatchWriter:
    def __init__(self) -> None:
        self.backups = BackupManager()
        self.diffs = DiffGenerator()
        self.planner = PatchPlanner()

    @log_performance("scoped_patch_writer.apply")
    def apply(self, repo_path: str, patches: PatchSet) -> PatchWriteResult:
        log_step("scoped_patch_writer_started", {"repo_path": repo_path})
        try:
            planned = self.planner.validate(patches)
            result = PatchWriteResult()
            for patch in planned.patches:
                path = self._resolve_safe_path(repo_path, patch.path)
                path.parent.mkdir(parents=True, exist_ok=True)
                before = path.read_text(encoding="utf-8") if path.exists() else ""
                after = self._apply_content(before, patch)
                self.backups.backup(path)
                path.write_text(after, encoding="utf-8")
                result.applied.append(
                    AppliedPatch(
                        path=patch.path,
                        operation=patch.operation,
                        diff=self.diffs.unified(before, after, patch.path),
                    )
                )
            log_metric("applied_patch_count", len(planned.patches))
            logger.info("Scoped patch writer completed")
            return result
        except Exception as exc:
            log_exception(exc, context={"repo_path": repo_path, "stage": "patch_writer"})
            raise

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
            insertion_index = len(lines)
            if patch.start_line is not None:
                insertion_index = min(max(patch.start_line - 1, 0), len(lines))
            prefix = "" if not before or before.endswith("\n") else "\n"
            if insertion_index == len(lines):
                return f"{before}{prefix}{content}"
            return "".join(lines[:insertion_index] + [content] + lines[insertion_index:])

        raise ValueError(f"Unsupported patch operation: {patch.operation}")
