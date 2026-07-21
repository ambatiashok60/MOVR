from __future__ import annotations

import subprocess
from worktop.core_services.app.utility.custom_logger.logging import logger




class GitTool:
    def head(self, repo_path: str) -> str | None:
        logger.info("[playwright-generation] stage=git_head status=started repo=%s", repo_path)
        try:
            result = subprocess.run(
                ["git", "-C", repo_path, "rev-parse", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
            )
            head = result.stdout.strip() or None
            logger.info("[playwright-generation] stage=git_head status=completed head=%s", head)
            return head
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=git_head status=failed repo=%s error=%s",
                repo_path,
                exc,
            )
            raise

    def diff(self, repo_path: str) -> str:
        result = subprocess.run(
            ["git", "-C", repo_path, "diff", "--"],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.stdout
