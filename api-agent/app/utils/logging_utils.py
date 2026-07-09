from __future__ import annotations

from typing import Any


try:
    from worktop.core_services.app.utility.custom_logger.log_helpers import (
        log_card_simple,
        log_exception,
        log_metric,
        log_step,
    )
    from worktop.core_services.app.utility.custom_logger.logging import (
        log_performance,
        logger,
    )
except Exception:
    import logging
    from collections.abc import Callable

    logger = logging.getLogger("api-agent")
    logging.basicConfig(level=logging.INFO)

    def log_step(name: str, context: dict[str, Any] | None = None) -> None:
        logger.info("%s %s", name, context or {})

    def log_metric(name: str, value: Any = None, context: dict[str, Any] | None = None) -> None:
        logger.info("%s=%s %s", name, value, context or {})

    def log_exception(exc: Exception, context: dict[str, Any] | None = None) -> None:
        logger.exception("%s %s", exc, context or {})

    def log_card_simple(
        title: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        logger.info("%s: %s %s", title, message, metadata or {})

    def log_performance(name: str) -> Callable:
        def decorator(func: Callable) -> Callable:
            return func

        return decorator


def build_log_context(**metadata: Any) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if value is not None}
