from __future__ import annotations

from pathlib import Path
from worktop.test_agent.utils.logging import get_logger


logger = get_logger(__name__)


class FileReaderTool:
    def read(self, repo_path: str, relative_path: str) -> str:
        logger.info(
            "[playwright-generation] stage=file_read status=started repo=%s path=%s",
            repo_path,
            relative_path,
        )
        try:
            path = Path(repo_path, relative_path).resolve()
            content = path.read_text(encoding="utf-8")
            logger.info(
                "[playwright-generation] stage=file_read status=completed bytes=%s path=%s",
                len(content.encode("utf-8")),
                relative_path,
            )
            return content
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=file_read status=failed repo=%s path=%s error=%s",
                repo_path,
                relative_path,
                exc,
            )
            raise
