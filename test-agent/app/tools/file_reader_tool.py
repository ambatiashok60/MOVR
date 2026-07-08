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


class FileReaderTool:
    @log_performance("file_reader_tool.read")
    def read(self, repo_path: str, relative_path: str) -> str:
        log_step("file_read_started", {"repo_path": repo_path, "stage": "file_read"})
        try:
            path = Path(repo_path, relative_path).resolve()
            content = path.read_text(encoding="utf-8")
            log_metric("file_read_bytes", len(content.encode("utf-8")))
            return content
        except Exception as exc:
            log_exception(exc, context={"repo_path": repo_path, "stage": "file_read"})
            raise
