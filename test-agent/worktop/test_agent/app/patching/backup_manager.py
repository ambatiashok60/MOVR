from __future__ import annotations

from pathlib import Path


class BackupManager:
    def backup(self, path: Path) -> Path | None:
        if not path.exists():
            return None
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        return backup_path
