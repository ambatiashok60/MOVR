from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str:
        ...

    def complete_structured(
        self,
        prompt: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        ...
