from __future__ import annotations

import logging
from collections.abc import Mapping
from time import perf_counter
from types import TracebackType
from typing import Any

from worktop.test_agent.utils.logging import (  # noqa: F401  (re-exported)
    DATE_FORMAT,
    LOG_FORMAT,
    configure_logging,
    get_logger,
    stage_log,
)


def format_kv(details: Mapping[str, Any] | None = None) -> str:
    if not details:
        return ""
    return " | ".join(
        f"{key}={_format_value(value)}"
        for key, value in details.items()
        if value is not None
    )


def log_event(
    logger: logging.Logger,
    level: int,
    stage: str,
    status: str,
    **details: Any,
) -> None:
    suffix = format_kv(details)
    message = f"[playwright-generation] stage={stage} | status={status}"
    if suffix:
        message = f"{message} | {suffix}"
    logger.log(level, message)


class TimedStage:
    def __init__(
        self,
        logger: logging.Logger,
        stage: str,
        *,
        level: int = logging.INFO,
        **details: Any,
    ) -> None:
        self.logger = logger
        self.stage = stage
        self.level = level
        self.details = details
        self.started_at = 0.0

    def __enter__(self) -> "TimedStage":
        self.started_at = perf_counter()
        log_event(self.logger, self.level, self.stage, "started", **self.details)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        duration_ms = round((perf_counter() - self.started_at) * 1000, 2)
        if exc is None:
            log_event(
                self.logger,
                self.level,
                self.stage,
                "completed",
                duration_ms=duration_ms,
                **self.details,
            )
            return False

        log_event(
            self.logger,
            logging.ERROR,
            self.stage,
            "failed",
            duration_ms=duration_ms,
            error=exc,
            **self.details,
        )
        return False


def _format_value(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return "[" + ", ".join(str(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{key}:{val}" for key, val in value.items()) + "}"
    return str(value)
