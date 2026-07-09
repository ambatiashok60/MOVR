from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class LocalFallbackLLMClient:
    """Non-production fallback for import/smoke-test environments.

    Real Worktop deployments should use WorktopModelClientAdapter.
    """

    def complete(self, prompt: str) -> str:
        return json.dumps({"message": "local fallback model response", "prompt_size": len(prompt)})

    def complete_structured(
        self,
        prompt: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        return response_model.model_validate({})
