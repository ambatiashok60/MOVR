from __future__ import annotations

from pathlib import Path
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


class FileWriterTool:
    @log_performance("file_writer_tool.write")
    def write(self, repo_path: str, relative_path: str, content: str) -> None:
        log_step("file_write_started", {"repo_path": repo_path, "stage": "file_write"})
        try:
            path = Path(repo_path, relative_path).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                path.with_suffix(path.suffix + ".bak").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            path.write_text(content, encoding="utf-8")
            log_metric("file_write_bytes", len(content.encode("utf-8")))
            logger.info("File write completed")
        except Exception as exc:
            log_exception(exc, context={"repo_path": repo_path, "stage": "file_write"})
            raise
