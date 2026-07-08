from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class DefaultLLMClientAdapter:
    def __init__(self, db: Any, tenant_id: str) -> None:
        from worktop.core_services.app.gen_ai_models.default_llm_client import DefaultLLMClient

        self._client = DefaultLLMClient(db=db, tenant_id=tenant_id)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        input_data = self._client.prepare_input(system_prompt=system_prompt, user_prompt=user_prompt)
        response = self._client.generate_completion(input_data)
        return self._extract_text(response)

    def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        text = self.complete(system_prompt=system_prompt, user_prompt=user_prompt)
        try:
            return response_model.model_validate_json(text)
        except Exception:
            return response_model.model_validate(json.loads(text))

    @property
    def provider(self) -> str | None:
        return getattr(self._client, "provider", None)

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
        return str(response)
