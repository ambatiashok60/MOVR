import threading

from app.ai_workspace.domain.execution_context import ExecutionContext


class InMemoryExecutionStore:
    """Not in the original file list — added because execution_routes.py's GET /executions/{id}
    and GET /executions/{id}/timeline endpoints need somewhere to read a completed execution
    from. ExecutionOrchestrator.run() previously returned an ExecutionContext that was then
    discarded once the HTTP response was sent, which makes those two GET endpoints impossible
    to implement honestly. Same in-memory/single-process caveat as the other stores here."""

    def __init__(self):
        self._executions: dict[str, ExecutionContext] = {}
        self._lock = threading.Lock()

    def save(self, execution: ExecutionContext) -> None:
        with self._lock:
            self._executions[execution.execution_id] = execution

    def get(self, execution_id: str) -> ExecutionContext | None:
        with self._lock:
            return self._executions.get(execution_id)
