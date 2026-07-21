"""Rendering helpers: the box-drawing "card" formatter and a JSON line formatter.

`format_log_card` accepts an arbitrary mapping so adding/removing fields never
breaks the formatter (per the design's requirement).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

_LABEL_WIDTH = 16


def _render_log_value(value: Any) -> str:
    if isinstance(value, Mapping):
        return "\n".join(f"{k}: {_render_log_value(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return "\n".join(f"- {_render_log_value(item)}" for item in value)
    return str(value)


def format_log_card(title: str, values: Mapping[str, Any], width: int = 74) -> str:
    inner = width - 4
    value_width = inner - _LABEL_WIDTH - 1
    lines = [
        f"╭{'─' * (width - 2)}╮",
        f"│ {title[:inner]:<{inner}} │",
        f"├{'─' * (width - 2)}┤",
    ]
    for key, value in values.items():
        label = str(key).replace("_", " ").title()[:_LABEL_WIDTH]
        rendered = _render_log_value(value)
        first, *rest = rendered.splitlines() or [""]
        lines.append(f"│ {label:<{_LABEL_WIDTH}} {first[:value_width]:<{value_width}} │")
        for cont in rest:
            lines.append(f"│ {'':<{_LABEL_WIDTH}} {cont[:value_width]:<{value_width}} │")
    lines.append(f"╰{'─' * (width - 2)}╯")
    return "\n".join(lines)


class CardConsoleFormatter(logging.Formatter):
    """Renders records that carry a `card` dict as a box; others plainly."""

    def format(self, record: logging.LogRecord) -> str:
        card = getattr(record, "card", None)
        if card is not None:
            return format_log_card(getattr(record, "card_title", record.getMessage()), card)
        return f"{record.levelname:<7} {record.getMessage()}"


class JsonFormatter(logging.Formatter):
    """Machine-readable line format for file/cloud handlers."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
        }
        for key in ("card", "correlation"):
            value = getattr(record, key, None)
            if value:
                payload.update(value if key == "correlation" else {"data": value})
        return json.dumps(payload, default=str)
