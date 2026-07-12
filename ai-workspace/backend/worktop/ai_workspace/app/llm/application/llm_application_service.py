from worktop.ai_workspace.app.llm.application.llm_gateway import LLMCompletion, LLMGateway
from worktop.ai_workspace.app.llm.application.llm_telemetry_service import LLMTelemetryService
from worktop.ai_workspace.app.llm.application.review_budget_service import ReviewBudgetService


class LLMApplicationService:
    """What every ai_workspace/ service calls for a normal (non-streaming) completion —
    chat_service.py and agent_service.py's planner both go through this rather than
    touching LLMGateway directly, so telemetry is never accidentally skipped."""

    def __init__(self, gateway: LLMGateway, telemetry: LLMTelemetryService, budget: ReviewBudgetService | None = None):
        self._gateway = gateway
        self._telemetry = telemetry
        self._budget = budget

    def complete(self, execution_id: str, system_prompt: str, user_prompt: str) -> LLMCompletion:
        completion = self._gateway.complete(system_prompt=system_prompt, user_prompt=user_prompt)
        self._telemetry.record_completion(execution_id=execution_id, completion=completion)
        if self._budget:
            self._budget.charge(execution_id, len(system_prompt) + len(user_prompt), len(completion.text or ""))
        return completion

    def budget_report(self, execution_id: str):
        return self._budget.report(execution_id) if self._budget else None
