from __future__ import annotations
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from app.ai_workspace.domain.file_change import FileChange, FileChangeStatus
from app.common.path_safety import resolve_within_root
from app.repository.application.file_write_service import FileWriteService

class RepositoryLockedError(RuntimeError): pass
class StaleProposalError(RuntimeError): pass

class WorkspaceTransactionService:
    """Lock, stale-check, snapshot, apply, journal, and rollback reviewed changes."""
    def __init__(self, root: str, writer: FileWriteService, stale_lock_seconds: float = 3600) -> None:
        self.root = Path(root) / "ai-workspace-transactions"
        self.writer = writer
        self.stale_lock_seconds = stale_lock_seconds

    def apply(self, run_id: str, workspace: str, changes: list[FileChange]) -> list[str]:
        lock = self._lock_path(workspace)
        self._acquire(lock, run_id)
        run_root = self.root / "runs" / run_id
        snapshot = run_root / "snapshot"
        journal = run_root / "journal.jsonl"
        applied: list[FileChange] = []
        try:
            self._verify_fresh(workspace, changes)
            for change in changes:
                target = resolve_within_root(workspace, change.file_path)
                if target.exists():
                    backup = snapshot / change.file_path
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    backup.write_bytes(target.read_bytes())
                self._record(journal, "snapshot", change.file_path)
            for change in changes:
                if change.status == FileChangeStatus.DELETED:
                    self.writer.delete(workspace, change.file_path)
                else:
                    self.writer.write(workspace, change.file_path, change.new_content)
                applied.append(change)
                self._record(journal, "applied", change.file_path)
            self._record(journal, "committed", f"{len(applied)} files")
            return [change.file_path for change in applied]
        except Exception:
            self._rollback(workspace, snapshot, applied, journal)
            raise
        finally:
            lock.unlink(missing_ok=True)

    def _verify_fresh(self, workspace: str, changes: list[FileChange]) -> None:
        for change in changes:
            target = resolve_within_root(workspace, change.file_path)
            exists = target.exists()
            content = target.read_bytes() if exists and target.is_file() else b""
            digest = hashlib.sha256(content).hexdigest()
            if exists != change.original_existed or digest != change.original_digest:
                raise StaleProposalError(f"{change.file_path} changed after the proposal was generated")

    def _rollback(self, workspace: str, snapshot: Path, applied: list[FileChange], journal: Path) -> None:
        for change in reversed(applied):
            target = resolve_within_root(workspace, change.file_path)
            backup = snapshot / change.file_path
            if backup.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(backup.read_bytes())
            elif target.exists():
                target.unlink()
            self._record(journal, "rolled_back", change.file_path)

    def _lock_path(self, workspace: str) -> Path:
        digest = hashlib.sha256(str(Path(workspace).resolve()).encode()).hexdigest()[:20]
        return self.root / "locks" / f"{digest}.lock"

    def _acquire(self, lock: Path, run_id: str) -> None:
        lock.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"run_id": run_id, "pid": os.getpid(), "created": time.time()})
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as handle: handle.write(payload)
        except FileExistsError:
            try: holder = json.loads(lock.read_text())
            except Exception: holder = {}
            if time.time() - float(holder.get("created", 0)) > self.stale_lock_seconds:
                lock.unlink(missing_ok=True)
                return self._acquire(lock, run_id)
            raise RepositoryLockedError(f"Repository is locked by run {holder.get('run_id', 'unknown')}")

    def _record(self, journal: Path, action: str, detail: str) -> None:
        journal.parent.mkdir(parents=True, exist_ok=True)
        with journal.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "action": action, "detail": detail}) + "\n")
