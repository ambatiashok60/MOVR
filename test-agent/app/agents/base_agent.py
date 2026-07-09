from __future__ import annotations

import logging
from typing import Any, TypeVar

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
logger = logging.getLogger(__name__)

__all__ = ["BaseAgent", "logger"]


class BaseAgent:
    agent_name = "base_agent"

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm = llm_client

    def log_start(self, stage: str, **metadata: Any) -> dict[str, Any]:
        context = build_log_context(stage=stage, agent_name=self.agent_name, **metadata)
        logger.info(
            "[playwright-generation] agent=%s stage=%s status=started context=%s",
            self.agent_name,
            stage,
            context,
        )
        return context

    def log_decision(self, title: str, message: str, **metadata: Any) -> None:
        logger.info(
            "[playwright-generation] decision=%s message=%s metadata=%s",
            title,
            message,
            metadata,
        )

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
            logger.exception(
                "[playwright-generation] agent=%s stage=llm_structured_completion status=failed error=%s",
                self.agent_name,
                exc,
            )
            raise
