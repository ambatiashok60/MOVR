from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from app.llm.llm_client import LLMClient
from app.utils.logging_utils import build_log_context, log_exception, log_step

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class BaseAgent:
    agent_name = "base_agent"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client

    def log_start(self, stage: str, **metadata: Any) -> dict[str, Any]:
        context = build_log_context(stage=stage, agent_name=self.agent_name, **metadata)
        log_step(f"{self.agent_name}_started", context)
        return context

    def complete_structured(
        self,
        prompt: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        if self.llm is None:
            raise RuntimeError("LLM client is required for API agent generation")
        try:
            return self.llm.complete_structured(prompt=prompt, response_model=response_model)
        except Exception as exc:
            log_exception(
                exc,
                context={"stage": "llm_structured_completion", "agent": self.agent_name},
            )
            raise
