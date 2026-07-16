from __future__ import annotations

from pathlib import Path
from worktop.core_services.app.utility.custom_logger.logging import logger




class FileWriterTool:
    def write(self, repo_path: str, relative_path: str, content: str) -> None:
        logger.info(
            "[playwright-generation] stage=file_write status=started repo=%s path=%s",
            repo_path,
            relative_path,
        )
        try:
            path = Path(repo_path, relative_path).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                path.with_suffix(path.suffix + ".bak").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            path.write_text(content, encoding="utf-8")
            logger.info(
                "[playwright-generation] stage=file_write status=completed bytes=%s path=%s",
                len(content.encode("utf-8")),
                relative_path,
            )
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=file_write status=failed repo=%s path=%s error=%s",
                repo_path,
                relative_path,
                exc,
            )
            raise
