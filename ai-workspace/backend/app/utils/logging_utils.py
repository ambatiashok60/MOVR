from __future__ import annotations

import logging
import time
from inspect import iscoroutinefunction
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger("ai_workspace")

try:
    from worktop.core_services.app.utility.custom_logger.log_helpers import (
        log_exception as _worktop_log_exception,
        log_metric as _worktop_log_metric,
        log_step as _worktop_log_step,
    )
    from worktop.core_services.app.utility.custom_logger.logging import (
        log_performance as _worktop_log_performance,
        logger as _worktop_logger,
    )

    logger = _worktop_logger
except ImportError:
    _worktop_log_exception = None
    _worktop_log_metric = None
    _worktop_log_step = None
    _worktop_log_performance = None

F = TypeVar("F", bound=Callable[..., Any])

LOG_METADATA_KEYS = (
    "session_id",
    "execution_id",
    "tenant_id",
    "repo_path",
    "workspace_path",
    "branch",
    "mode",
    "stage",
    "run_id",
    "file_id",
    "state_backend",
)


def build_log_context(**metadata: Any) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if key in LOG_METADATA_KEYS and value is not None}


def log_step(event: str, context: dict[str, Any] | None = None) -> None:
    if _worktop_log_step:
        _worktop_log_step(event, context or {})
        return
    logger.info(event, extra={"context": context or {}})


def log_metric(name: str, value: Any) -> None:
    if _worktop_log_metric:
        _worktop_log_metric(name, value)
        return
    logger.info("metric", extra={"metric": name, "value": value})


def log_exception(exc: Exception, context: dict[str, Any] | None = None) -> None:
    if _worktop_log_exception:
        _worktop_log_exception(exc, context=context or {})
        return
    logger.exception("ai_workspace_exception", extra={"context": context or {}})


def log_performance(name: str) -> Callable[[F], F]:
    if _worktop_log_performance:
        return _worktop_log_performance(name)

    def decorator(func: F) -> F:
        if iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                started = time.perf_counter()
                try:
                    return await func(*args, **kwargs)
                finally:
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    logger.info("performance", extra={"operation": name, "elapsed_ms": elapsed_ms})

            return async_wrapper  # type: ignore[return-value]

        @wraps(func)
        def wrapper(*args, **kwargs):
            started = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - started) * 1000
                logger.info("performance", extra={"operation": name, "elapsed_ms": elapsed_ms})

        return wrapper  # type: ignore[return-value]

    return decorator
