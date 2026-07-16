from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ChatMessage:
    id: str
    session_id: str
    role: ChatRole
    content: str
    created_at: datetime
    execution_id: str | None = None
