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


class GitTool:
    @log_performance("git_tool.head")
    def head(self, repo_path: str) -> str | None:
        log_step("git_head_started", {"repo_path": repo_path, "stage": "git"})
        try:
            result = subprocess.run(
                ["git", "-C", repo_path, "rev-parse", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip() or None
        except Exception as exc:
            log_exception(exc, context={"repo_path": repo_path, "stage": "git"})
            raise

    @log_performance("git_tool.diff")
    def diff(self, repo_path: str) -> str:
        result = subprocess.run(
            ["git", "-C", repo_path, "diff", "--"],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.stdout
