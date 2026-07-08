from __future__ import annotations

from typing import Any, TypeVar

from worktop.core_services.app.gen_ai_models.model_client_factory import (
    ModelClientFactory,
)
from worktop.core_services.app.dao.models_config_dao import (
    ModelsConfigurationDAO,
)
from worktop.core_services.app.utility.common_utils import CommonUtils
from worktop.core_services.app.utility.custom_logger.log_helpers import (
    log_card_simple,
    log_exception,
    log_metric,
    log_step,
)
from worktop.core_services.app.utility.custom_logger.logging import (
    log_performance,
    logger,
)

try:
    from worktop.core_services.app.models.llm_telemetry import (
        TelemetryFeature,
        TelemetrySubFeature,
    )
    from worktop.core_services.app.services.llm_telemetry_service import trace_llm

    _TELEMETRY_AVAILABLE = True
except ImportError:
    trace_llm = None
    TelemetryFeature = None
    TelemetrySubFeature = None
    _TELEMETRY_AVAILABLE = False

from app.utils.logging_utils import build_log_context

ResponseModel = TypeVar("ResponseModel")


class BaseAgent:
    agent_name = "base_agent"

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm = llm_client

    def log_start(self, stage: str, **metadata: Any) -> dict[str, Any]:
        context = build_log_context(stage=stage, agent_name=self.agent_name, **metadata)
        log_step(f"{self.agent_name}_started", context)
        return context

    def log_decision(self, title: str, message: str, **metadata: Any) -> None:
        log_card_simple(title=title, message=message, metadata=metadata)

    def complete_structured(
        self,
        prompt: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        if self.llm is None:
            raise RuntimeError(
                "LLM client is required for this agentic Playwright generation "
                "process. Fast-failing because no real model client is available."
            )
        try:
            return self.llm.complete_structured(prompt=prompt, response_model=response_model)
        except Exception as exc:
            log_exception(exc, context={"stage": "llm_structured_completion", "agent_name": self.agent_name})
            raise
