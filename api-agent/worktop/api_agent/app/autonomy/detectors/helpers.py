from __future__ import annotations

import hashlib
from pathlib import Path

from worktop.api_agent.app.schemas.autonomy import CapabilityRecord, EvidenceRecord, EvidenceType


def evidence_id(detector: str, capability: str, path: str | None, signal: str) -> str:
    raw = f"{detector}|{capability}|{path or ''}|{signal}"
    return f"ev-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def create_detection(
    detector: str,
    revision: str,
    category: str,
    capability: str,
    evidence_type: EvidenceType,
    signal: str,
    confidence: float,
    path: Path | None = None,
    line: int | None = None,
) -> tuple[EvidenceRecord, CapabilityRecord]:
    relative = str(path) if path else None
    item_id = evidence_id(detector, capability, relative, signal)
    evidence = EvidenceRecord(
        evidence_id=item_id,
        capability=capability,
        evidence_type=evidence_type,
        source_file=relative,
        start_line=line,
        end_line=line,
        signal=signal,
        confidence=confidence,
        detector=detector,
        repository_revision=revision,
    )
    capability_record = CapabilityRecord(
        capability_id=capability,
        category=category,
        name=capability,
        confidence=confidence,
        evidence_ids=[item_id],
    )
    return evidence, capability_record


def iter_source_files(root: Path, suffixes: set[str], limit: int = 2000):
    count = 0
    skipped = {".git", "node_modules", "target", "build", "dist", ".venv", "__pycache__"}
    for path in root.rglob("*"):
        if count >= limit:
            return
        if not path.is_file() or path.suffix.lower() not in suffixes or any(part in skipped for part in path.parts):
            continue
        count += 1
        yield path
