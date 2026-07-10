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
            return self._parse_structured_response(text, response_model)
        except Exception as first_exc:
            log_step(
                "api_agent_llm_structured_repairing",
                {
                    "tenant_id": self.tenant_id,
                    "response_model": response_model.__name__,
                    "error": str(first_exc)[:500],
                },
            )
            repaired_text = self.complete(
                self._build_repair_prompt(prompt, text, response_model, first_exc)
            )
            try:
                return self._parse_structured_response(repaired_text, response_model)
            except Exception as exc:
                log_exception(
                    exc,
                    context={
                        "tenant_id": self.tenant_id,
                        "stage": "llm_structured_parse",
                        "response_model": response_model.__name__,
                        "first_error": str(first_exc)[:500],
                    },
                )
                raise

    def _parse_structured_response(
        self,
        text: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        try:
            return response_model.model_validate_json(text)
        except Exception:
            payload = self._load_json_document(text)
            return response_model.model_validate(payload)

    def _load_json_document(self, text: str) -> Any:
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return json.loads(self._extract_first_json_document(stripped))

    def _extract_first_json_document(self, text: str) -> str:
        start = next((index for index, char in enumerate(text) if char in "{["), None)
        if start is None:
            raise ValueError("LLM response did not contain a JSON object or array")
        stack: list[str] = []
        in_string = False
        escaped = False
        pairs = {"{": "}", "[": "]"}
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char in pairs:
                stack.append(pairs[char])
            elif stack and char == stack[-1]:
                stack.pop()
                if not stack:
                    return text[start : index + 1]
        raise ValueError("LLM response contained incomplete JSON")

    def _build_repair_prompt(
        self,
        original_prompt: str,
        raw_response: str,
        response_model: type[ResponseModel],
        error: Exception,
    ) -> str:
        schema = json.dumps(response_model.model_json_schema(), indent=2)
        return f"""
You are repairing a previous structured LLM response.

The previous response failed Pydantic validation for {response_model.__name__}.
Return only one valid JSON object. Do not include markdown fences or prose.
Use only fields from the schema.

Validation error:
{str(error)[:4000]}

JSON schema:
{schema}

Original task prompt:
{original_prompt[:12000]}

Previous invalid response:
{raw_response[:8000]}
""".strip()

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
