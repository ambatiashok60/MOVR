from __future__ import annotations

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


class TsAstParserTool:
    @log_performance("ts_ast_parser_tool.parse")
    def parse(self, file_path: str, content: str) -> dict[str, Any]:
        log_step("ts_ast_parse_started", {"stage": "ts_ast_parse"})
        try:
            return {"file_path": file_path, "exports": [], "imports": []}
        except Exception as exc:
            log_exception(exc, context={"stage": "ts_ast_parse"})
            raise
