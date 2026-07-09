from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel

from app.utils.logging_utils import log_exception, log_step, logger

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class WorktopModelClientAdapter:
    """Adapter around Worktop's configured model client.

    The preferred path is DefaultLLMClient because it already encapsulates model
    configuration lookup through Worktop's ModelsConfigurationDAO and
    ModelClientFactory. A direct ModelClientFactory fallback is kept for older
    installations where DefaultLLMClient is not available but model utilities
    are.
    """

    def __init__(self, db: Any, tenant_id: int | str) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self._client = self._create_client()

    def complete(self, prompt: str) -> str:
        log_step(
            "api_agent_llm_completion_started",
            {"tenant_id": self.tenant_id, "stage": "llm"},
        )
        input_data = self._prepare_input(prompt)
        response = self._generate_completion(input_data)
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
            try:
                return response_model.model_validate(json.loads(text))
            except Exception as exc:
                log_exception(
                    exc,
                    context={
                        "tenant_id": self.tenant_id,
                        "stage": "llm_structured_parse",
                        "response_model": response_model.__name__,
                    },
                )
                raise

    def _create_client(self) -> Any:
        try:
            from worktop.core_services.app.gen_ai_models.default_llm_client import (
                DefaultLLMClient,
            )

            return DefaultLLMClient(db=self.db, tenant_id=self.tenant_id)
        except Exception as exc:
            logger.info("DefaultLLMClient unavailable, trying direct ModelClientFactory path")
            return self._create_direct_model_client(exc)

    def _create_direct_model_client(self, original_exc: Exception) -> Any:
        try:
            from worktop.core_services.app.dao.models_config_dao import (
                ModelsConfigurationDAO,
            )
            from worktop.core_services.app.gen_ai_models.model_client_factory import (
                ModelClientFactory,
            )
            from worktop.core_services.app.utility.common_utils import CommonUtils

            model_info = CommonUtils.load_model_info(self.db, self.tenant_id)
            model_config = ModelsConfigurationDAO(self.db).get_model_config_by_tenant_id(
                self.tenant_id
            )
            model_params = model_info.get("model_params", {}) if isinstance(model_info, dict) else {}
            provider = (
                model_config.get("provider_name")
                if isinstance(model_config, dict)
                else getattr(model_config, "provider_name", None)
            )
            return ModelClientFactory.get_client(
                provider,
                model_config,
                model_params,
                self.db,
                self.tenant_id,
            )
        except Exception as exc:
            log_exception(
                exc,
                context={
                    "tenant_id": self.tenant_id,
                    "stage": "direct_model_client_factory",
                    "original_error": str(original_exc),
                },
            )
            raise RuntimeError("Unable to create Worktop model client") from exc

    def _prepare_input(self, prompt: str) -> Any:
        if hasattr(self._client, "prepare_input"):
            return self._client.prepare_input(system_prompt="", user_prompt=prompt)
        return prompt

    def _generate_completion(self, input_data: Any) -> Any:
        if hasattr(self._client, "generate_completion"):
            return self._client.generate_completion(input_data)
        if hasattr(self._client, "complete"):
            return self._client.complete(input_data)
        if hasattr(self._client, "invoke"):
            return self._client.invoke(input_data)
        raise RuntimeError("Configured model client does not expose a supported completion method")

    def _extract_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            for key in ("content", "text", "response", "completion", "message"):
                value = response.get(key)
                if isinstance(value, str):
                    return value
        text = getattr(response, "content", None) or getattr(response, "text", None)
        if isinstance(text, str):
            return text
        return str(response)
