from __future__ import annotations

from pathlib import Path


from worktop.test_agent.app.patching.backup_manager import BackupManager
from worktop.test_agent.app.patching.diff_generator import DiffGenerator
from worktop.test_agent.app.patching.patch_planner import PatchPlanner
from worktop.test_agent.app.schemas.code_patch import AppliedPatch, PatchSet, PatchWriteResult
from worktop.test_agent.utils.logging import get_logger

logger = get_logger(__name__)


class ScopedPatchWriter:
    def __init__(self) -> None:
        self.backups = BackupManager()
        self.diffs = DiffGenerator()
        self.planner = PatchPlanner()

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
                before = path.read_text(encoding="utf-8") if path.exists() else ""
                after = self._apply_content(before, patch)
                backup_path = self.backups.backup(path)
                path.write_text(after, encoding="utf-8")
                result.applied.append(
                    AppliedPatch(
                        path=patch.path,
                        operation=patch.operation,
                        diff=self.diffs.unified(before, after, patch.path),
                        backup_path=str(backup_path) if backup_path else None,
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
        root = Path(repo_path).resolve()
        for applied in reversed(result.applied):
            path = self._resolve_safe_path(repo_path, applied.path)
            backup_path = Path(applied.backup_path).resolve() if applied.backup_path else None
            if backup_path and backup_path.exists() and root in backup_path.parents:
                path.write_text(backup_path.read_text(encoding="utf-8"), encoding="utf-8")
                logger.info(
                    "[playwright-generation] stage=patch_writer_rollback status=restored path=%s backup=%s",
                    applied.path,
                    backup_path,
                )
            elif applied.operation == "create" and path.exists():
                path.unlink()
                logger.info(
                    "[playwright-generation] stage=patch_writer_rollback status=removed_created_file path=%s",
                    applied.path,
                )
            else:
                logger.warning(
                    "[playwright-generation] stage=patch_writer_rollback status=skipped path=%s backup=%s",
                    applied.path,
                    backup_path,
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
            insertion_index = len(lines)
            if patch.start_line is not None:
                insertion_index = min(max(patch.start_line - 1, 0), len(lines))
            prefix = "" if not before or before.endswith("\n") else "\n"
            if insertion_index == len(lines):
                return f"{before}{prefix}{content}"
            return "".join(lines[:insertion_index] + [content] + lines[insertion_index:])

        raise ValueError(f"Unsupported patch operation: {patch.operation}")
