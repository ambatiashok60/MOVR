from app.llm.application.llm_gateway import LLMCompletion, LLMGateway
from app.llm.application.llm_telemetry_service import LLMTelemetryService


class LLMApplicationService:
    """What every ai_workspace/ service calls for a normal (non-streaming) completion —
    chat_service.py and agent_service.py's planner both go through this rather than
    touching LLMGateway directly, so telemetry is never accidentally skipped."""

    def __init__(self, gateway: LLMGateway, telemetry: LLMTelemetryService):
        self._gateway = gateway
        self._telemetry = telemetry

    def complete(self, execution_id: str, system_prompt: str, user_prompt: str) -> LLMCompletion:
        completion = self._gateway.complete(system_prompt=system_prompt, user_prompt=user_prompt)
        self._telemetry.record_completion(execution_id=execution_id, completion=completion)
        return completion
