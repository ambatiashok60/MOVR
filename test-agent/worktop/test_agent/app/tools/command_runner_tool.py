from __future__ import annotations

import subprocess
from worktop.test_agent.utils.logging import get_logger


logger = get_logger(__name__)


class CommandRunnerTool:
    def run(self, repo_path: str, command: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
        logger.info(
            "[playwright-generation] stage=command_run status=started repo=%s command=%s",
            repo_path,
            command,
        )
        try:
            result = subprocess.run(
                command,
                cwd=repo_path,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            logger.info(
                "[playwright-generation] stage=command_run status=completed exit_code=%s",
                result.returncode,
            )
            return result
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=command_run status=failed repo=%s command=%s error=%s",
                repo_path,
                command,
                exc,
            )
            raise
