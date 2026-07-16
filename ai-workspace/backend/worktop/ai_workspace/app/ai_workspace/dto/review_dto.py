from .base import CamelModel


class DiffLineDto(CamelModel):
    type: str
    old_line_number: int | None = None
    new_line_number: int | None = None
    content: str


class DiffHunkDto(CamelModel):
    header: str
    lines: list[DiffLineDto]


class FileChangeDto(CamelModel):
    # Deliberately no `new_content` field — the frontend only ever needs the diff for display
    # and never round-trips full file content back on Apply (server-staged, see
    # FileChange.new_content's docstring in ai_workspace/domain/file_change.py).
    id: str
    run_id: str
    file_path: str
    status: str
    additions: int
    deletions: int
    diff_hunks: list[DiffHunkDto]
    decision: str


class ReviewDecisionRequest(CamelModel):
    run_id: str
    file_id: str
    decision: str  # "kept" | "rejected"


class ApplyChangesRequest(CamelModel):
    run_id: str
    kept_file_ids: list[str]


class ApplyChangesResponse(CamelModel):
    applied_file_paths: list[str]
