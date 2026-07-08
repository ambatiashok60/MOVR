from datetime import datetime

from .base import CamelModel


class CreateSessionRequest(CamelModel):
    repository_id: str
    branch: str


class SessionDto(CamelModel):
    id: str
    repository_id: str
    branch: str
    mode: str
    current_task: str | None = None
    started_at: datetime
    last_activity_at: datetime
