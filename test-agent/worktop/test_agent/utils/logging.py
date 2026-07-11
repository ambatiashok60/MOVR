from __future__ import annotations

import logging
import os
from time import perf_counter
from types import TracebackType

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | "
    "%(filename)s:%(lineno)d::%(funcName)s | "
    "%(name)s | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
BANNER = "=" * 60
_LOG_LEVEL_ENV = "PLAYWRIGHT_AGENT_LOG_LEVEL"

_configured = False


def configure_logging(level: int | None = None) -> None:
    """Configure root logging once for the whole service.

    Idempotent: modules call get_logger() at import time in any order, and the
    first call wins; uvicorn's handlers are re-formatted so the console shows
    one consistent format.
    """
    global _configured
    if level is None:
        level_name = os.getenv(_LOG_LEVEL_ENV, "INFO").upper()
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
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """The one supported way to obtain a logger.

    Every module does `logger = get_logger(__name__)`; the module path becomes
    the logger name, and logging configuration is guaranteed to be in place.
    """
    if not _configured:
        configure_logging()
    return logging.getLogger(name)


def _title(stage: str) -> str:
    return stage.replace("_", " ").strip().title()


class StageLog:
    """Standardized stage logging: banner on start, decision section, timing.

    Renders the workflow log convention every orchestrator stage follows::

        ============================================================
        Repository Analysis
        ============================================================

        Starting repository analysis...

        Decision
        --------
        Repository successfully analyzed.

        Completed in 2.31 seconds.
    """

    def __init__(
        self,
        logger: logging.Logger,
        stage: str,
        *,
        level: int = logging.INFO,
        **context: object,
    ) -> None:
        self.logger = logger
        self.stage = stage
        self.title = _title(stage)
        self.level = level
        self.context = {k: v for k, v in context.items() if v is not None}
        self.started_at = 0.0

    def __enter__(self) -> "StageLog":
        self.started_at = perf_counter()
        context = (
            "\n" + "\n".join(f"{key}: {value}" for key, value in self.context.items())
            if self.context
            else ""
        )
        self.logger.log(
            self.level,
            "\n%s\n%s\n%s\n\nStarting %s...%s",
            BANNER,
            self.title,
            BANNER,
            self.title.lower(),
            context,
            stacklevel=2,
        )
        return self

    def detail(self, message: str, *args: object) -> None:
        self.logger.log(self.level, message, *args, stacklevel=2)

    def decision(self, decision: str, reasoning: str | None = None) -> None:
        body = decision if not reasoning else f"{decision}\n\nReasoning: {reasoning}"
        self.logger.log(self.level, "\nDecision\n--------\n%s", body, stacklevel=2)

    def section(self, heading: str, body: str) -> None:
        self.logger.log(
            self.level, "\n%s\n%s\n%s", heading, "-" * len(heading), body,
            stacklevel=2,
        )

    @property
    def elapsed_seconds(self) -> float:
        return perf_counter() - self.started_at

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        elapsed = self.elapsed_seconds
        if exc is None:
            self.logger.log(
                self.level,
                "%s completed in %.2f seconds.",
                self.title,
                elapsed,
                stacklevel=2,
            )
        else:
            self.logger.error(
                "%s FAILED after %.2f seconds: %s: %s",
                self.title,
                elapsed,
                type(exc).__name__,
                exc,
                stacklevel=2,
            )
        return False


def stage_log(
    logger: logging.Logger,
    stage: str,
    *,
    level: int = logging.INFO,
    **context: object,
) -> StageLog:
    return StageLog(logger, stage, level=level, **context)
