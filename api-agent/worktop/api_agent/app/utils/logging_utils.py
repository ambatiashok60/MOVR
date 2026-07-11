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
    # Outside the worktop platform the same call sites fall back to the
    # standardized service logging (same format, levels, and stage banners).
    from collections.abc import Callable
    from functools import wraps
    from time import perf_counter

    from worktop.api_agent.utils.logging import get_logger

    logger = get_logger("worktop.api_agent")

    def log_step(name: str, context: dict[str, Any] | None = None) -> None:
        suffix = (
            " | " + " | ".join(f"{key}={value}" for key, value in context.items())
            if context
            else ""
        )
        logger.info("%s%s", name, suffix, stacklevel=2)

    def log_metric(name: str, value: Any = None, context: dict[str, Any] | None = None) -> None:
        logger.info("metric %s=%s %s", name, value, context or {}, stacklevel=2)

    def log_exception(exc: Exception, context: dict[str, Any] | None = None) -> None:
        logger.exception("%s %s", exc, context or {}, stacklevel=2)

    def log_card_simple(
        title: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        body = message + (f"\n{metadata}" if metadata else "")
        logger.info("\n%s\n%s\n%s", title, "-" * len(title), body, stacklevel=2)

    def log_performance(name: str) -> Callable:
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                started_at = perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    logger.info(
                        "%s completed in %.2f seconds.",
                        name,
                        perf_counter() - started_at,
                    )

            return wrapper

        return decorator


def build_log_context(**metadata: Any) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if value is not None}
