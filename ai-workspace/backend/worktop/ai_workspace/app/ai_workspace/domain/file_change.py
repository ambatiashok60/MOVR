from dataclasses import dataclass, field
from enum import Enum

from .review_decision import ReviewDecision


class FileChangeStatus(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class DiffLine:
    type: str  # "context" | "added" | "removed"
    old_line_number: int | None
    new_line_number: int | None
    content: str


@dataclass
class DiffHunk:
    header: str
    lines: list[DiffLine] = field(default_factory=list)


@dataclass
class FileChange:
    """`new_content` is the source of truth for what apply_patch_tool.py writes to disk.
    `diff_hunks` is a display-only derivative computed by diff_service.py — reconstructing
    file content by concatenating hunk lines is lossy (a unified diff's context window doesn't
    cover the whole file), so nothing should ever do that. Always write `new_content` verbatim."""

    id: str
    run_id: str
    file_path: str
    status: FileChangeStatus
    additions: int
    deletions: int
    new_content: str
    diff_hunks: list[DiffHunk]
    decision: ReviewDecision = ReviewDecision.PENDING
    original_digest: str = ""
    original_existed: bool = False
