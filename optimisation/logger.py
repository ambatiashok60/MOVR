from __future__ import annotations

import logging
import os
from typing import TextIO

CRISP_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d::%(funcName)s | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_LEVEL_ENV = "REFERENCE_LOG_LEVEL"


def configure_logging(
    level: int | None = None,
    stream: TextIO | None = None,
) -> None:
    """Reference configuration only; call once at an application's entry point."""
    if level is None:
        level_name = os.getenv(LOG_LEVEL_ENV, "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)
    if root.handlers:
        return

    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(CRISP_FORMAT, datefmt=DATE_FORMAT))
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a module logger; this helper emits no records and hides no call sites."""
    if not logging.getLogger().handlers:
        configure_logging()
    return logging.getLogger(name)
