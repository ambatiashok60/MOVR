from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


def _compact_parts(*parts: str) -> str:
    return "; ".join(part for part in parts if part)


def _stringify_item(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if {"from_state", "to_state"} & value.keys():
            transition = " -> ".join(
                str(value[key])
                for key in ("from_state", "to_state")
                if value.get(key)
            )
            trigger = (
                f"trigger: {value['trigger']}"
                if value.get("trigger")
                else ""
            )
            outcome = (
                f"expected outcome: {value['expected_outcome']}"
                if value.get("expected_outcome")
                else ""
            )
            return _compact_parts(transition, trigger, outcome)
        if "description" in value:
            kind = f"{value['type']}: " if value.get("type") else ""
            return f"{kind}{value['description']}"
        if "step" in value:
            return str(value["step"])
        return ", ".join(f"{key}: {val}" for key, val in value.items())
    return str(value)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_stringify_item(item) for item in value]
    return [_stringify_item(value)]


class FunctionalIntent(BaseModel):
    capability: str = ""
    actor: str = ""
    journey: list[str] = Field(default_factory=list)
    state_transitions: list[str] = Field(default_factory=list)
    assertions: list[str] = Field(default_factory=list)

    @field_validator("journey", "state_transitions", "assertions", mode="before")
    @classmethod
    def normalize_string_lists(cls, value: Any) -> list[str]:
        return _string_list(value)
