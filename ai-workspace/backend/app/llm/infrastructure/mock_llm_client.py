from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class MockLLMClient:
    provider = "mock"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if "ONLY a single JSON object" in system_prompt:
            return '{"plan": {"steps": []}, "file_changes": []}'
        return (
            "Mock AI Workspace response. Set AI_WORKSPACE_ALLOW_MOCK_LLM=false and wire "
            "DefaultLLMClient for real model output."
        )

    def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        return response_model.model_validate(json.loads(self.complete(system_prompt, user_prompt)))
