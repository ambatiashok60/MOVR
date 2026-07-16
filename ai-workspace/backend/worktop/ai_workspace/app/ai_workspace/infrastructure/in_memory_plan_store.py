import threading

from worktop.ai_workspace.app.ai_workspace.domain.execution_plan import ExecutionPlan


class InMemoryPlanStore:
    """Stores the model-generated plan for a completed Agent run."""

    def __init__(self):
        self._plans: dict[str, ExecutionPlan] = {}
        self._lock = threading.Lock()

    def save(self, plan: ExecutionPlan) -> None:
        with self._lock:
            self._plans[plan.execution_id] = plan

    def get(self, execution_id: str) -> ExecutionPlan | None:
        with self._lock:
            return self._plans.get(execution_id)

    def delete(self, execution_id: str) -> None:
        with self._lock:
            self._plans.pop(execution_id, None)
