"""Group ranked candidate files into token-bounded context batches (§10)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from app.context.token_estimator import estimate_tokens


@dataclass
class ContextBatch:
    batch_id: str
    objective: str
    files: list[str] = field(default_factory=list)
    estimated_tokens: int = 0
    status: str = "pending"
    summary: str | None = None


def build_batches(workspace: Path, ranked_files: list[str], objective: str) -> list[ContextBatch]:
    batches: list[ContextBatch] = []
    current = ContextBatch(batch_id=f"batch_{uuid.uuid4().hex[:6]}", objective=objective)
    for rel in ranked_files:
        path = workspace / rel
        try:
            tokens = estimate_tokens(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            tokens = 0
        over_files = len(current.files) >= settings.max_files_per_context_batch
        over_tokens = current.estimated_tokens + tokens > settings.max_context_tokens_per_batch
        if current.files and (over_files or over_tokens):
            batches.append(current)
            current = ContextBatch(batch_id=f"batch_{uuid.uuid4().hex[:6]}", objective=objective)
        current.files.append(rel)
        current.estimated_tokens += tokens
    if current.files:
        batches.append(current)
    return batches
