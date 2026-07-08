from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel

from worktop.core_services.app.utility.custom_logger.log_helpers import (
    log_exception,
    log_step,
)
from worktop.core_services.app.utility.custom_logger.logging import logger

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class DefaultLLMClientAdapter:
    def __init__(self, db: Any, tenant_id: str) -> None:
        from worktop.core_services.app.gen_ai_models.default_llm_client import (
            DefaultLLMClient,
        )

        self._client = DefaultLLMClient(db=db, tenant_id=tenant_id)

    def complete(self, prompt: str) -> str:
        log_step("llm_completion_started", {"stage": "llm"})
        input_data = self._client.prepare_input(system_prompt="", user_prompt=prompt)
        response = self._client.generate_completion(input_data)
        return self._extract_text(response)

    def complete_structured(
        self,
        prompt: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        text = self.complete(prompt)
        try:
            return response_model.model_validate_json(text)
        except Exception:
            return response_model.model_validate(json.loads(text))

    def _extract_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            for key in ("content", "text", "response", "completion"):
                value = response.get(key)
                if isinstance(value, str):
                    return value
        text = getattr(response, "content", None) or getattr(response, "text", None)
        if isinstance(text, str):
            return text
        logger.info("LLM response type did not expose a known text field")
        return str(response)
