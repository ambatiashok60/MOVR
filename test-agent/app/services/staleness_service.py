from __future__ import annotations

from typing import Any

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


class StalenessService:
    @log_performance("staleness_service.is_stale")
    def is_stale(self, repo_head: str | None, cached_head: str | None) -> bool:
        log_step("staleness_check_started", {"repo_head": repo_head})
        try:
            stale = repo_head != cached_head
            logger.info("Inventory staleness checked")
            return stale
        except Exception as exc:
            log_exception(exc, context={"stage": "staleness"})
            raise
