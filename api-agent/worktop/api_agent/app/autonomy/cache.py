from __future__ import annotations

import hashlib
from pathlib import Path

from worktop.api_agent.app.schemas.autonomy import CapabilityAssessment


class CapabilityAssessmentCache:
    def __init__(self) -> None:
        self._items: dict[str, CapabilityAssessment] = {}

    def revision(self, root: Path, detector_versions: dict[str, str]) -> str:
        digest = hashlib.sha256()
        digest.update(str(root.resolve()).encode())
        digest.update(repr(sorted(detector_versions.items())).encode())
        skipped = {".git", "node_modules", "target", "build", "dist", ".venv", "__pycache__"}
        for path in sorted(root.rglob("*")):
            if not path.is_file() or any(part in skipped for part in path.parts):
                continue
            stat = path.stat()
            digest.update(str(path.relative_to(root)).encode()); digest.update(str(stat.st_size).encode()); digest.update(str(stat.st_mtime_ns).encode())
        return digest.hexdigest()[:24]

    def get(self, revision: str) -> CapabilityAssessment | None:
        item = self._items.get(revision)
        if item is None:
            return None
        copy = item.model_copy(deep=True); copy.cache_hit = True
        return copy

    def put(self, revision: str, assessment: CapabilityAssessment) -> None:
        self._items[revision] = assessment.model_copy(deep=True)
