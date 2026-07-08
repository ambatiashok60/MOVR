from __future__ import annotations

import json
from typing import Any


def as_json(data: Any) -> str:
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    return json.dumps(data, indent=2, default=str)


def response_contract(model_name: str) -> str:
    return (
        "Return only valid JSON. Do not include markdown fences or prose. "
        f"The JSON must match the {model_name} response schema."
    )
