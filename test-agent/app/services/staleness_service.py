from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


class StalenessService:
    def is_stale(self, repo_head: str | None, cached_head: str | None) -> bool:
        logger.info(
            "[playwright-generation] stage=staleness status=started repo_head=%s cached_head=%s",
            repo_head,
            cached_head,
        )
        try:
            stale = repo_head != cached_head
            logger.info("[playwright-generation] stage=staleness status=completed stale=%s", stale)
            return stale
        except Exception as exc:
            logger.exception("[playwright-generation] stage=staleness status=failed error=%s", exc)
            raise
