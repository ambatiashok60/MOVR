from __future__ import annotations


class ApiAgentError(Exception):
    """Base exception for API agent failures."""


class TaskNotFoundError(ApiAgentError):
    def __init__(self, task_id: str) -> None:
        super().__init__(f"Task not found: {task_id}")
        self.task_id = task_id


class AbortRequestedError(ApiAgentError):
    def __init__(self, task_id: str) -> None:
        super().__init__(f"Abort requested for task: {task_id}")
        self.task_id = task_id


class UnsafeWorkspacePathError(ApiAgentError):
    def __init__(self, path: str) -> None:
        super().__init__(f"Workspace path is not safe or does not exist: {path}")
        self.path = path
