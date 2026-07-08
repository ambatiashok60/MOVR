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

from app.schemas.repo_profile import RepoProfile
from app.schemas.technology_profile import TechnologyProfile


class TechnologyIntelligenceService:
    @log_performance("technology_intelligence_service.detect")
    def detect(self, repo_profile: RepoProfile) -> TechnologyProfile:
        log_step("technology_intelligence_started", {"repo_path": repo_profile.repo_path})
        try:
            profile = TechnologyProfile()
            logger.info("Technology intelligence completed")
            return profile
        except Exception as exc:
            log_exception(exc, context={"repo_path": repo_profile.repo_path, "stage": "technology"})
            raise
