from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.ai_workspace.domain.tool_definition import ToolDefinition


@dataclass
class ToolExecutionContext:
    """Everything a tool needs to run, threaded in by tool_execution_service.py — tools never
    reach into global state or re-derive the workspace path themselves."""

    workspace_path: str
    tenant_id: str


class BaseTool(ABC):
    @property
    @abstractmethod
    def definition(self) -> ToolDefinition: ...

    @abstractmethod
    def execute(self, context: ToolExecutionContext, arguments: dict) -> dict:
        """Returns a JSON-serializable result dict — this is what gets summarized back into
        the agent plan's tool_calls[].result_summary on the frontend side."""
        ...
