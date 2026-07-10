from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.logging_config import log_event
from app.schemas.code_patch import PatchSet, PatchWriteResult

logger = logging.getLogger(__name__)


class WorkspaceLockedError(RuntimeError):
    """Another job holds the repository lock; running now would interleave
    writes and validate the wrong files."""

    def __init__(self, repo_path: str, holder: dict[str, object]) -> None:
        super().__init__(
            f"Repository {repo_path} is locked by job "
            f"{holder.get('job_id', 'unknown')} (since {holder.get('acquired_at', '?')})."
        )
        self.holder = holder


@dataclass(frozen=True)
class JobWorkspace:
    job_id: str
    repo_path: str
    root: Path
    patch_journal: Path
    rollback_journal: Path
    snapshot_dir: Path
    lock_file: Path


class WorkspaceManager:
    """Give each generation job an isolated workspace and a repository lock.

    Two jobs on the same repository would otherwise interleave patch writes
    and validate each other's files. The lock serializes jobs per repository;
    the journals and snapshots record exactly what this job touched so its
    changes are auditable and reversible independent of any other job.
    """

    def __init__(self, workspace_root: str | None = None) -> None:
        self.root = Path(workspace_root or settings.workspace_root) / "test-agent-workspaces"
        self.stale_lock_seconds = settings.workspace_stale_lock_seconds

    def acquire(self, job_id: str, repo_path: str) -> JobWorkspace:
        workspace_dir = self.root / job_id
        snapshot_dir = workspace_dir / "snapshot"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        lock_file = self._lock_path(repo_path)
        self._acquire_lock(lock_file, job_id, repo_path)
        workspace = JobWorkspace(
            job_id=job_id,
            repo_path=repo_path,
            root=workspace_dir,
            patch_journal=workspace_dir / "patch-journal.jsonl",
            rollback_journal=workspace_dir / "rollback-journal.jsonl",
            snapshot_dir=snapshot_dir,
            lock_file=lock_file,
        )
        log_event(
            logger,
            logging.INFO,
            "workspace",
            "acquired",
            job_id=job_id,
            repo=repo_path,
            workspace=str(workspace_dir),
        )
        return workspace

    def release(self, workspace: JobWorkspace) -> None:
        try:
            holder = self._read_lock(workspace.lock_file)
            if holder.get("job_id") == workspace.job_id:
                workspace.lock_file.unlink(missing_ok=True)
                log_event(
                    logger,
                    logging.INFO,
                    "workspace",
                    "released",
                    job_id=workspace.job_id,
                    repo=workspace.repo_path,
                )
        except OSError as exc:
            log_event(
                logger,
                logging.WARNING,
                "workspace",
                "release_failed",
                job_id=workspace.job_id,
                error=exc,
            )

    def snapshot_targets(self, workspace: JobWorkspace, patches: PatchSet) -> None:
        """Copy the pre-patch content of every target file into the workspace."""
        root = Path(workspace.repo_path)
        for patch in patches.patches:
            source = root / patch.path
            if not source.is_file():
                continue
            destination = workspace.snapshot_dir / patch.path
            if destination.exists():
                continue  # first snapshot wins: it is the pre-job state
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                source.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8"
            )

    def record_patches(self, workspace: JobWorkspace, result: PatchWriteResult) -> None:
        for applied in result.applied:
            self._append(
                workspace.patch_journal,
                {
                    "job_id": workspace.job_id,
                    "path": applied.path,
                    "operation": applied.operation,
                    "backup_path": applied.backup_path,
                    "at": self._now(),
                },
            )

    def record_rollback(self, workspace: JobWorkspace, result: PatchWriteResult) -> None:
        for applied in result.applied:
            self._append(
                workspace.rollback_journal,
                {
                    "job_id": workspace.job_id,
                    "path": applied.path,
                    "operation": applied.operation,
                    "at": self._now(),
                },
            )

    def _acquire_lock(self, lock_file: Path, job_id: str, repo_path: str) -> None:
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "job_id": job_id,
                "repo_path": repo_path,
                "pid": os.getpid(),
                "acquired_at": self._now(),
                "acquired_monotonic": time.time(),
            }
        )
        while True:
            try:
                descriptor = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(descriptor, "w") as handle:
                    handle.write(payload)
                return
            except FileExistsError:
                holder = self._read_lock(lock_file)
                acquired = float(holder.get("acquired_monotonic", 0) or 0)
                if acquired and time.time() - acquired > self.stale_lock_seconds:
                    log_event(
                        logger,
                        logging.WARNING,
                        "workspace",
                        "stale_lock_reclaimed",
                        job_id=job_id,
                        stale_holder=holder.get("job_id", "unknown"),
                    )
                    lock_file.unlink(missing_ok=True)
                    continue
                raise WorkspaceLockedError(repo_path, holder) from None

    def _read_lock(self, lock_file: Path) -> dict[str, object]:
        try:
            return json.loads(lock_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _lock_path(self, repo_path: str) -> Path:
        digest = hashlib.sha256(str(Path(repo_path).resolve()).encode()).hexdigest()[:16]
        return self.root / "locks" / f"{digest}.lock"

    def _append(self, journal: Path, record: dict[str, object]) -> None:
        journal.parent.mkdir(parents=True, exist_ok=True)
        with journal.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
