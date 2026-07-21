from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from worktop.core_services.app.utility.custom_logger.logging import logger

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)

# Only structured-parsing / validation failures should trigger the single repair
# attempt. Transport, configuration and provider failures must propagate as-is so
# the caller sees the real error instead of a misleading "repair" round-trip.
EXPECTED_STRUCTURED_EXCEPTIONS = (
    ValueError,
    TypeError,
    json.JSONDecodeError,
    ValidationError,
)


class DefaultLLMClientAdapter:
    """Test-agent facing adapter over Worktop's configured model client.

    Client construction follows one explicit Worktop integration path: shared
    model parameters and decrypted tenant configuration are loaded first, then
    ``ModelClientFactory.get_client`` creates the provider client. The adapter
    never instantiates or probes the higher-level Worktop ``DefaultLLMClient``.

    Responsibilities that belong here: the ``complete`` / ``complete_structured``
    contract, structured-response validation, one repair attempt, and generic
    metadata logging. Provider SDK calls, payload construction, credentials and
    tenant model selection all belong to the Worktop infrastructure below.
    """

    def __init__(self, db: Any, tenant_id: int | str) -> None:
        self._db = db
        self._tenant_id = self._normalize_tenant_id(tenant_id)
        self._model_params = self._load_model_params()
        self._model_config = self._load_model_config()
        self._provider = self._resolve_provider(self._model_config)
        self._client = self._create_client()

    # ------------------------------------------------------------------ #
    # Public contract
    # ------------------------------------------------------------------ #
    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        if not prompt or not prompt.strip():
            raise ValueError("prompt cannot be empty")

        logger.debug(
            "LLM completion started: provider=%s tenant_id=%s",
            self._provider,
            self._tenant_id,
        )
        try:
            input_data = self._prepare_input(prompt, system_prompt or "")
            response = self._generate_completion(input_data)
            text = self._extract_text(response)
            if not text or not text.strip():
                raise ValueError("LLM provider returned an empty response")
            logger.debug(
                "LLM completion finished: provider=%s chars=%s",
                self._provider,
                len(text),
            )
            return text
        except Exception as exc:
            logger.exception(
                "LLM completion failed: provider=%s tenant_id=%s",
                self._provider,
                self._tenant_id,
            )
            raise RuntimeError(
                f"LLM completion failed for provider {self._provider}"
            ) from exc

    def complete_structured(
        self,
        prompt: str,
        response_model: type[ResponseModel],
        system_prompt: str | None = None,
    ) -> ResponseModel:
        logger.debug(
            "Structured completion started (model schema: %s)",
            response_model.__name__,
        )
        structured_prompt = self._build_structured_prompt(prompt, response_model)
        text = self.complete(structured_prompt, system_prompt=system_prompt)
        try:
            parsed = self._parse_structured_response(text, response_model)
            logger.debug(
                "Structured completion parsed cleanly (%s)", response_model.__name__
            )
            return parsed
        except EXPECTED_STRUCTURED_EXCEPTIONS as first_exc:
            logger.warning(
                "Structured response for %s failed to parse; attempting repair: %s",
                response_model.__name__,
                first_exc,
            )
            repair_prompt = self._build_repair_prompt(
                original_prompt=prompt,
                raw_response=text,
                response_model=response_model,
                error=first_exc,
            )
            repaired_text = self.complete(
                repair_prompt,
                system_prompt=(
                    "Repair the response into valid JSON matching the supplied "
                    "schema. Return JSON only."
                ),
            )
            try:
                parsed = self._parse_structured_response(repaired_text, response_model)
                logger.warning(
                    "Structured response for %s recovered after repair.",
                    response_model.__name__,
                )
                return parsed
            except EXPECTED_STRUCTURED_EXCEPTIONS as exc:
                logger.error(
                    "stage=llm_structured_parse status=failed response_model=%s "
                    "first_error=%s error=%s",
                    response_model.__name__,
                    first_exc,
                    exc,
                )
                raise

    @property
    def provider(self) -> str | None:
        return self._provider

    # ------------------------------------------------------------------ #
    # Client construction (Worktop wiring)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize_tenant_id(tenant_id: int | str) -> int:
        if isinstance(tenant_id, bool):  # bool is a subclass of int; reject it
            raise ValueError("tenant_id must be an integer, not a boolean")
        if isinstance(tenant_id, int):
            return tenant_id
        if isinstance(tenant_id, str):
            stripped = tenant_id.strip()
            if not stripped:
                raise ValueError("tenant_id cannot be empty")
            try:
                return int(stripped)
            except ValueError as exc:
                raise ValueError(
                    f"tenant_id must be numeric, got {tenant_id!r}"
                ) from exc
        raise ValueError(f"Unsupported tenant_id type: {type(tenant_id)!r}")

    def _create_client(self) -> Any:
        from worktop.core_services.app.gen_ai_models.model_client_factory import (
            ModelClientFactory,
        )

        return ModelClientFactory.get_client(
            self._provider,
            self._model_config,
            self._model_params,
            self._db,
            self._tenant_id,
        )

    def _load_model_params(self) -> dict[str, Any]:
        """Load shared Worktop model parameters using the host utility contract."""
        from worktop.core_services.app.utility.common_utils import CommonUtils

        model_info = CommonUtils.load_model_info(self._db, self._tenant_id)
        if not isinstance(model_info, dict):
            raise TypeError("Worktop model information must be a dictionary")
        model_params = model_info.get("model_params", {})
        if not isinstance(model_params, dict):
            raise TypeError("Worktop model_params must be a dictionary")
        return model_params

    def _load_model_config(self) -> Any:
        """Load tenant model configuration using the current Worktop DAO contract."""
        from worktop.core_services.app.dao.models_config_dao import (
            ModelsConfigurationDAO,
        )

        model_config = ModelsConfigurationDAO(self._db).get_model_config_by_tenant_id(
            self._tenant_id
        )
        if model_config is None:
            raise RuntimeError(
                f"No model configuration found for tenant {self._tenant_id}"
            )
        return model_config

    def _resolve_provider(self, model_config: Any) -> str:
        if isinstance(model_config, dict):
            provider = model_config.get("provider_name", "")
        else:
            provider = getattr(model_config, "provider_name", "")
        provider = str(provider or "").strip()
        if not provider:
            raise RuntimeError(
                f"No provider_name configured for tenant {self._tenant_id}"
            )
        return provider

    # ------------------------------------------------------------------ #
    # Provider invocation (ownership stays with the factory-created client)
    # ------------------------------------------------------------------ #
    def _prepare_input(self, prompt: str, system_prompt: str) -> Any:
        return self._client.prepare_input(
            system_prompt=system_prompt, user_prompt=prompt
        )

    def _generate_completion(self, input_data: Any) -> Any:
        return self._client.generate_completion(input_data)

    # ------------------------------------------------------------------ #
    # Response normalization
    # ------------------------------------------------------------------ #
    def _extract_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            text = self._extract_text_from_mapping(response)
            if text:
                return text
        if isinstance(response, list):
            text = self._extract_text_from_blocks(response)
            if text:
                return text
        text = getattr(response, "content", None) or getattr(response, "text", None)
        if isinstance(text, str):
            return text
        if isinstance(text, list):
            joined = self._extract_text_from_blocks(text)
            if joined:
                return joined
        raise TypeError(
            "LLM provider response did not expose a supported text field "
            f"(type={type(response).__name__})"
        )

    def _extract_text_from_mapping(self, response: dict[str, Any]) -> str | None:
        for key in ("content", "text", "response", "completion", "message"):
            value = response.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                nested = self._extract_text_from_mapping(value)
                if nested:
                    return nested
            if isinstance(value, list):
                nested = self._extract_text_from_blocks(value)
                if nested:
                    return nested

        choices = response.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if isinstance(choice, dict):
                    nested = self._extract_text_from_mapping(choice)
                    if nested:
                        return nested
        return None

    def _extract_text_from_blocks(self, blocks: list[Any]) -> str | None:
        """Join provider content blocks such as Anthropic's ``[{type,text}, ...]``."""
        parts: list[str] = []
        for block in blocks:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
                else:
                    nested = self._extract_text_from_mapping(block)
                    if nested:
                        parts.append(nested)
            else:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        joined = "".join(parts)
        return joined or None

    # ------------------------------------------------------------------ #
    # Structured parsing helpers
    # ------------------------------------------------------------------ #
    def _build_structured_prompt(
        self,
        prompt: str,
        response_model: type[ResponseModel],
    ) -> str:
        schema = json.dumps(response_model.model_json_schema(), indent=2)
        return (
            f"{prompt}\n\n"
            "Return exactly one valid JSON document. Do not include markdown "
            "fences or explanatory prose.\n"
            "The response must conform to this JSON schema:\n"
            f"{schema}"
        ).strip()

    def _parse_structured_response(
        self,
        text: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        try:
            return response_model.model_validate_json(text)
        except ValidationError:
            payload = self._load_json_document(text)
            return response_model.model_validate(payload)

    def _load_json_document(self, text: str) -> Any:
        stripped = text.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            document = self._extract_first_json_document(stripped)
            return json.loads(document)

    def _extract_first_json_document(self, text: str) -> str:
        start = next(
            (index for index, char in enumerate(text) if char in "{["),
            None,
        )
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
Use only fields from the schema. For arrays whose item type is string, return
strings only, not nested objects.

Validation error:
{self._truncate(str(error), limit=4000)}

JSON schema:
{schema}

Original task prompt:
{self._truncate(original_prompt, limit=12000)}

Previous invalid response:
{self._truncate(raw_response, limit=8000)}
""".strip()

    def _truncate(self, value: str, limit: int = 2000) -> str:
        if len(value) <= limit:
            return value
        return f"{value[:limit]}... [truncated]"
