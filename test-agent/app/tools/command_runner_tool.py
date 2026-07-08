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


class CommandRunnerTool:
    @log_performance("command_runner_tool.run")
    def run(self, repo_path: str, command: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
        log_step("command_run_started", {"repo_path": repo_path, "stage": "command_run"})
        try:
            result = subprocess.run(
                command,
                cwd=repo_path,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            log_metric("command_exit_code", result.returncode)
            return result
        except Exception as exc:
            log_exception(exc, context={"repo_path": repo_path, "stage": "command_run"})
            raise
