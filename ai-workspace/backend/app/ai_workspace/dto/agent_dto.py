from .base import CamelModel
from .execution_dto import ExecutionRunDto


class AgentRunRequest(CamelModel):
    session_id: str
    repository_id: str
    branch: str
    prompt: str
    context_file_paths: list[str] = []


class AgentRunResponse(CamelModel):
    run: ExecutionRunDto
