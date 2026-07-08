from __future__ import annotations

import subprocess
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


class SearchTool:
    @log_performance("search_tool.search")
    def search(self, repo_path: str, pattern: str) -> list[str]:
        log_step("search_started", {"repo_path": repo_path, "stage": "search"})
        try:
            result = subprocess.run(
                ["rg", "--line-number", pattern, repo_path],
                check=False,
                capture_output=True,
                text=True,
            )
            lines = result.stdout.splitlines()
            log_metric("search_result_count", len(lines))
            return lines
        except Exception as exc:
            log_exception(exc, context={"repo_path": repo_path, "stage": "search"})
            raise
