from datetime import datetime

from .base import CamelModel


class ChatRequest(CamelModel):
    session_id: str
    repository_id: str
    branch: str
    prompt: str
    context_file_paths: list[str] = []


class ChatMessageDto(CamelModel):
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime
    execution_id: str | None = None


class ChatResponse(CamelModel):
    message: ChatMessageDto
