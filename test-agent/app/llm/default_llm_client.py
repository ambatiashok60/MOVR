from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

from pydantic import BaseModel

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
logger = logging.getLogger(__name__)


class DefaultLLMClientAdapter:
    def __init__(self, db: Any, tenant_id: str) -> None:
        from worktop.core_services.app.gen_ai_models.default_llm_client import (
            DefaultLLMClient,
        )

        self._client = DefaultLLMClient(db=db, tenant_id=tenant_id)

    def complete(self, prompt: str) -> str:
        logger.info("[playwright-generation] stage=llm_completion status=started")
        input_data = self._client.prepare_input(system_prompt="", user_prompt=prompt)
        response = self._client.generate_completion(input_data)
        text = self._extract_text(response)
        logger.info(
            "[playwright-generation] stage=llm_completion status=completed response_chars=%s",
            len(text),
        )
        return text

    def complete_structured(
        self,
        prompt: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        logger.info(
            "[playwright-generation] stage=llm_structured_completion "
            f"status=started response_model={response_model.__name__}"
        )
        text = self.complete(prompt)
        try:
            parsed = self._parse_structured_response(text, response_model)
            logger.info(
                "[playwright-generation] stage=llm_structured_completion "
                f"status=completed response_model={response_model.__name__} repair=false"
            )
            return parsed
        except Exception as first_exc:
            logger.info(
                "[playwright-generation] stage=llm_structured_completion "
                f"status=repairing response_model={response_model.__name__} "
                f"error={first_exc}"
            )
            repair_prompt = self._build_repair_prompt(
                original_prompt=prompt,
                raw_response=text,
                response_model=response_model,
                error=first_exc,
            )
            repaired_text = self.complete(repair_prompt)
            try:
                parsed = self._parse_structured_response(repaired_text, response_model)
                logger.info(
                    "[playwright-generation] stage=llm_structured_completion "
                    f"status=completed response_model={response_model.__name__} repair=true"
                )
                return parsed
            except Exception as exc:
                logger.info(
                    "[playwright-generation] stage=llm_structured_completion "
                    f"status=failed response_model={response_model.__name__} error={exc}"
                )
                logger.exception(
                    "[playwright-generation] stage=llm_structured_parse status=failed "
                    "response_model=%s first_error=%s raw_response=%s repair_response=%s error=%s",
                    response_model.__name__,
                    first_exc,
                    self._truncate(text),
                    self._truncate(repaired_text),
                    exc,
                )
                raise

    def _extract_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            text = self._extract_text_from_mapping(response)
            if text:
                return text
        text = getattr(response, "content", None) or getattr(response, "text", None)
        if isinstance(text, str):
            return text
        logger.info("LLM response type did not expose a known text field")
        return str(response)

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

    def _extract_text_from_mapping(self, response: dict[str, Any]) -> str | None:
        for key in ("content", "text", "response", "completion", "message"):
            value = response.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                nested = self._extract_text_from_mapping(value)
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

    def _truncate(self, value: str, limit: int = 2000) -> str:
        if len(value) <= limit:
            return value
        return f"{value[:limit]}... [truncated]"
