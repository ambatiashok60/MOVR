from __future__ import annotations

import logging
import subprocess


logger = logging.getLogger(__name__)


class SearchTool:
    def search(self, repo_path: str, pattern: str) -> list[str]:
        logger.info(
            "[playwright-generation] stage=search status=started repo=%s pattern=%s",
            repo_path,
            pattern,
        )
        try:
            result = subprocess.run(
                ["rg", "--line-number", pattern, repo_path],
                check=False,
                capture_output=True,
                text=True,
            )
            lines = result.stdout.splitlines()
            logger.info(
                "[playwright-generation] stage=search status=completed results=%s",
                len(lines),
            )
            return lines
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=search status=failed repo=%s pattern=%s error=%s",
                repo_path,
                pattern,
                exc,
            )
            raise
