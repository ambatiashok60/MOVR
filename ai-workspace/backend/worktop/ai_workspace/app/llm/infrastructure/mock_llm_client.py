from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class MockLLMClient:
    provider = "mock"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if "evidence-driven coding agent" in system_prompt:
            return json.dumps({
                "status": "ready_to_patch",
                "reasoning_summary": "Prepared a safe demonstration change from repository context.",
                "root_cause": "Preview mode demonstrates the complete discovery, proposal, validation, and review contract.",
                "evidence": ["AI Workspace preview uses the explicit mock provider", "Changes remain staged until review"],
                "tool_calls": [],
                "plan": {"steps": [{"description": "Create a preview integration note", "affected_files": ["AI_WORKSPACE_PREVIEW.md"], "confidence": 0.95}]},
                "file_changes": [{
                    "path": "AI_WORKSPACE_PREVIEW.md", "status": "added",
                    "new_content": "# AI Workspace Preview\n\nThis staged file demonstrates Agent Mode review and Apply.\n",
                    "rationale": "Provide a visible, reversible preview patch.",
                    "evidence": ["Explicit preview-mode request"]
                }],
                "final_summary": "A safe preview file is ready for review."
            })
        if "ONLY a single JSON object" in system_prompt:
            return '{"plan": {"steps": []}, "file_changes": []}'
        return (
            "Mock Ask response: the selected repository context is available. In Worktop, "
            "replace this explicit mock provider with DefaultLLMClient for grounded answers."
        )

    def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        return response_model.model_validate(json.loads(self.complete(system_prompt, user_prompt)))
