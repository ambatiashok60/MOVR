from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
import json

WIDTH = 72
HEAVY = "="
LIGHT = "-"


def card(
    title: str,
    *,
    status: str | None = None,
    fields: Mapping[str, Any] | None = None,
    decision: str | None = None,
    reasoning: str | None = None,
    details: Iterable[str] | None = None,
    width: int = WIDTH,
) -> str:
    """Build a readable multiline log message without emitting a log record."""
    lines = ["", HEAVY * width, _heading(title, status), HEAVY * width]

    visible_fields = [(key, value) for key, value in (fields or {}).items() if value is not None]
    if visible_fields:
        lines.extend(["", *_field_lines(visible_fields)])

    if decision:
        lines.extend(["", "Decision", LIGHT * len("Decision"), decision])
    if reasoning:
        lines.extend(["", "Reasoning", LIGHT * len("Reasoning"), reasoning])

    visible_details = [str(item) for item in (details or []) if str(item).strip()]
    if visible_details:
        lines.extend(["", "Details", LIGHT * len("Details")])
        lines.extend(f"  • {item}" for item in visible_details)

    return "\n".join(lines)


def summary_card(
    title: str,
    *,
    outcome: str,
    metrics: Mapping[str, Any] | None = None,
    findings: Iterable[str] | None = None,
    duration_seconds: float | None = None,
) -> str:
    fields: dict[str, Any] = {"Outcome": outcome}
    fields.update(metrics or {})
    if duration_seconds is not None:
        fields["Duration"] = f"{duration_seconds:.2f}s"
    return card(title, status="COMPLETE", fields=fields, details=findings)


def failure_card(
    title: str,
    *,
    error: BaseException | str,
    fields: Mapping[str, Any] | None = None,
    recovery: str | None = None,
) -> str:
    return card(
        title,
        status="FAILED",
        fields=fields,
        decision=f"{type(error).__name__}: {error}" if isinstance(error, BaseException) else error,
        reasoning=recovery,
    )


def compact_event(event: str, **fields: Any) -> str:
    """Build one searchable line for high-volume events."""
    values = [event]
    values.extend(f"{key}={_compact(value)}" for key, value in fields.items() if value is not None)
    return " | ".join(values)


def minimal_card(title: str, message: str, *, status: str = "INFO", width: int = 72) -> str:
    heading = f" {title} [{status}] "
    return f"\n{heading:{LIGHT}^{width}}\n{message}"


def timeline_card(title: str, stages: Iterable[tuple[str, str, str]], *, current: str | None = None) -> str:
    icons = {"done": "✓", "running": "▶", "review": "!", "failed": "✕", "pending": "○"}
    lines = ["", HEAVY * WIDTH, title, HEAVY * WIDTH, ""]
    for stage, status, detail in stages:
        marker = icons.get(status.lower(), "•")
        active = "  ← current" if current == stage else ""
        lines.append(f"{marker} {stage:<26} {status.upper():<9} {detail}{active}")
    return "\n".join(lines)


def progress_card(title: str, *, completed: int, total: int, label: str = "Progress", width: int = 30, fields: Mapping[str, Any] | None = None) -> str:
    ratio = min(max(completed / total if total else 0.0, 0.0), 1.0)
    filled = round(ratio * width)
    bar = "█" * filled + "░" * (width - filled)
    values = {label: f"[{bar}] {ratio * 100:.0f}% ({completed}/{total})", **(fields or {})}
    return card(title, status="RUNNING", fields=values)


def comparison_card(title: str, rows: Iterable[tuple[str, Any, Any]], *, left_label: str = "Before", right_label: str = "After") -> str:
    prepared = [(str(name), str(left), str(right)) for name, left, right in rows]
    name_width = max([len("Metric"), *(len(row[0]) for row in prepared)])
    left_width = max([len(left_label), *(len(row[1]) for row in prepared)])
    header = f"{'Metric':<{name_width}} | {left_label:<{left_width}} | {right_label}"
    lines = ["", HEAVY * WIDTH, title, HEAVY * WIDTH, "", header, LIGHT * len(header)]
    lines.extend(f"{name:<{name_width}} | {left:<{left_width}} | {right}" for name, left, right in prepared)
    return "\n".join(lines)


def review_card(title: str, *, approved: Iterable[str] = (), findings: Iterable[str] = (), blocked: Iterable[str] = ()) -> str:
    groups = (("Approved", "✓", approved), ("Needs review", "!", findings), ("Blocked", "✕", blocked))
    lines = ["", HEAVY * WIDTH, f"{title}  [REVIEW]", HEAVY * WIDTH]
    for heading, icon, items in groups:
        visible = [str(item) for item in items]
        if visible:
            lines.extend(["", heading, LIGHT * len(heading), *(f"{icon} {item}" for item in visible)])
    return "\n".join(lines)


def audit_card(title: str, events: Iterable[Mapping[str, Any]]) -> str:
    lines = ["", HEAVY * WIDTH, f"{title}  [AUDIT]", HEAVY * WIDTH, ""]
    for index, event in enumerate(events, 1):
        lines.append(f"{index:02d}. {event.get('action', 'event'):<24} actor={event.get('actor', 'system')}  {event.get('detail', '')}")
    return "\n".join(lines)


def json_event(event: str, **fields: Any) -> str:
    return json.dumps({"event": event, **fields}, default=str, separators=(",", ":"), sort_keys=True)


def _heading(title: str, status: str | None) -> str:
    return f"{title}  [{status}]" if status else title


def _field_lines(fields: list[tuple[str, Any]]) -> list[str]:
    label_width = max(len(key) for key, _ in fields)
    return [f"{key:<{label_width}} : {value}" for key, value in fields]


def _compact(value: Any) -> str:
    rendered = str(value).replace("\n", " ").strip()
    return f'"{rendered}"' if " " in rendered else rendered
