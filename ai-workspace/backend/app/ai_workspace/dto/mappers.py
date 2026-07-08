"""Domain -> DTO mapping, shared by ai_workspace_routes.py and execution_routes.py (both need
to render an ExecutionContext + its FileChanges into the same ExecutionRunDto shape). Kept as
plain functions rather than methods on the DTOs themselves, since the DTOs are pure Pydantic
data and shouldn't know about domain types."""

from app.ai_workspace.domain.execution_context import ExecutionContext
from app.ai_workspace.domain.file_change import FileChange
from app.ai_workspace.dto.execution_dto import ExecutionRunDto, ExecutionStageDto
from app.ai_workspace.dto.review_dto import DiffHunkDto, DiffLineDto, FileChangeDto


def file_change_to_dto(change: FileChange) -> FileChangeDto:
    return FileChangeDto(
        id=change.id,
        run_id=change.run_id,
        file_path=change.file_path,
        status=change.status.value,
        additions=change.additions,
        deletions=change.deletions,
        diff_hunks=[
            DiffHunkDto(
                header=hunk.header,
                lines=[
                    DiffLineDto(
                        type=line.type,
                        old_line_number=line.old_line_number,
                        new_line_number=line.new_line_number,
                        content=line.content,
                    )
                    for line in hunk.lines
                ],
            )
            for hunk in change.diff_hunks
        ],
        decision=change.decision.value,
    )


def execution_to_dto(execution: ExecutionContext, file_changes: list[FileChange]) -> ExecutionRunDto:
    return ExecutionRunDto(
        id=execution.execution_id,
        session_id=execution.session_id,
        status=execution.status.value,
        stages=[
            ExecutionStageDto(id=s.id, label=s.label, status=s.status.value, detail=s.detail)
            for s in execution.stages
        ],
        files_changed=[file_change_to_dto(f) for f in file_changes],
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        error_message=execution.error_message,
    )
