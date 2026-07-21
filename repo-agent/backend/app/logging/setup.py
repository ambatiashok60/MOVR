"""Install the dual-handler logging configuration once at startup."""

from __future__ import annotations

import logging
import sys

from app.logging.formatter import CardConsoleFormatter, JsonFormatter

_CONFIGURED = False


def configure_logging(level: int = logging.INFO, json_path: str | None = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger("repo_agent")
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler(stream=sys.stdout)
    console.setFormatter(CardConsoleFormatter())
    root.addHandler(console)

    if json_path:
        file_handler = logging.FileHandler(json_path)
        file_handler.setFormatter(JsonFormatter())
        root.addHandler(file_handler)

    root.propagate = False
    _CONFIGURED = True
