from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class LLMClient(Protocol):
    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        ...

    def complete_structured(
        self,
        prompt: str,
        response_model: type[ResponseModel],
        system_prompt: str | None = None,
    ) -> ResponseModel:
        ...
