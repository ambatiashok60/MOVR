from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from time import perf_counter
from types import TracebackType
from typing import Any

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | "
    "%(filename)s:%(lineno)d::%(funcName)s | "
    "%(name)s | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: int | None = None) -> None:
    if level is None:
        level_name = os.getenv("PLAYWRIGHT_AGENT_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        configured_logger = logging.getLogger(logger_name)
        configured_logger.setLevel(level)
        for handler in configured_logger.handlers:
            handler.setFormatter(formatter)


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
