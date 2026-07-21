"""High-level, intention-revealing logging API used across services.

Services pass structured dicts; this module decides how they render (a card on
the console, JSON to file). Correlation ids are attached automatically.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from app.logging.context import current_correlation

_log = logging.getLogger("repo_agent")


class AgentLogger:
    def _emit(self, event: str, title: str, card: Mapping[str, Any] | None = None) -> None:
        _log.info(
            event,
            extra={
                "event": event,
                "card_title": title,
                "card": dict(card) if card else None,
                "correlation": current_correlation(),
            },
        )

    # --- run lifecycle -----------------------------------------------------
    def run_started(self, data: Mapping[str, Any]) -> None:
        self._emit("run_started", "AGENT RUN STARTED", data)

    def run_completed(self, data: Mapping[str, Any]) -> None:
        self._emit("run_completed", "AGENT RUN COMPLETED", data)

    def run_failed(self, data: Mapping[str, Any]) -> None:
        self._emit("run_failed", "AGENT RUN FAILED", data)

    def run_cancelled(self, data: Mapping[str, Any]) -> None:
        self._emit("run_cancelled", "AGENT RUN CANCELLED", data)

    def run_marked_stale(self, data: Mapping[str, Any]) -> None:
        self._emit("run_marked_stale", "AGENT RUN MARKED STALE", data)

    # --- planning ----------------------------------------------------------
    def plan_created(self, data: Mapping[str, Any]) -> None:
        self._emit("plan_created", "EXECUTION PLAN CREATED", data)

    def plan_updated(self, data: Mapping[str, Any]) -> None:
        self._emit("plan_updated", "EXECUTION PLAN UPDATED", data)

    # --- tools -------------------------------------------------------------
    def tool_started(self, data: Mapping[str, Any]) -> None:
        self._emit("tool_started", "TOOL CALL STARTED", data)

    def tool_completed(self, data: Mapping[str, Any]) -> None:
        self._emit("tool_completed", "TOOL CALL", data)

    def tool_failed(self, data: Mapping[str, Any]) -> None:
        self._emit("tool_failed", "TOOL CALL FAILED", data)

    # --- aws ---------------------------------------------------------------
    def aws_refresh_started(self, data: Mapping[str, Any]) -> None:
        self._emit("aws_reauthentication_required", "AWS SESSION REFRESH", data)

    def aws_refresh_completed(self, data: Mapping[str, Any]) -> None:
        self._emit("aws_reauthenticated", "AWS SESSION RESTORED", data)

    # --- validation / compaction ------------------------------------------
    def validation_completed(self, data: Mapping[str, Any]) -> None:
        self._emit("validation_completed", "VALIDATION COMPLETED", data)

    def compaction_completed(self, data: Mapping[str, Any]) -> None:
        self._emit("conversation_compaction_completed", "CONVERSATION COMPACTED", data)

    # --- generic -----------------------------------------------------------
    def event(self, event: str, data: Mapping[str, Any] | None = None) -> None:
        self._emit(event, event.replace("_", " ").upper(), data)


agent_logger = AgentLogger()
