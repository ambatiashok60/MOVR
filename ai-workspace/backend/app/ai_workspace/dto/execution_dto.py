from datetime import datetime

from .review_dto import FileChangeDto
from .base import CamelModel


class ExecutionStageDto(CamelModel):
    id: str
    label: str
    status: str
    detail: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExecutionRunDto(CamelModel):
    id: str
    session_id: str
    status: str
    stages: list[ExecutionStageDto]
    files_changed: list[FileChangeDto]
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    needs_review: bool = False
    review_reasons: list[str] = []
    budget_usage: dict[str, int | float] = {}
    engineering_review: dict = {}
    isolated_workspace_path: str | None = None


class ExecutionEventDto(CamelModel):
    execution_id: str
    event_type: str
    label: str
    detail: str | None = None
    created_at: datetime
