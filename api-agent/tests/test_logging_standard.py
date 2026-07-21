from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

from worktop.api_agent.utils.logging import BANNER, LOG_FORMAT, get_logger, stage_log

PACKAGE_ROOT = Path(__file__).parent.parent / "worktop" / "api_agent"
LOGGING_UTIL = PACKAGE_ROOT / "utils" / "logging.py"


def _package_modules() -> list[Path]:
    return [
        path
        for path in PACKAGE_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


class TestGetLogger:
    def test_get_logger_returns_module_named_logger(self) -> None:
        logger = get_logger("worktop.api_agent.app.services.some_service")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "worktop.api_agent.app.services.some_service"

    def test_log_format_carries_source_location(self) -> None:
        get_logger(__name__)

        assert logging.getLogger().handlers
        for token in ("%(filename)s", "%(lineno)d", "%(funcName)s", "%(name)s"):
            assert token in LOG_FORMAT


class TestStageLogFormat:
    def test_stage_renders_banner_decision_and_duration(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        logger = get_logger(__name__)
        with caplog.at_level(logging.INFO):
            with stage_log(logger, "scenario_generation", task_id="task-1") as log:
                log.decision(
                    "Generated 6 scenarios.",
                    reasoning="Story covers list, filter, and auth behaviors.",
                )

        output = "\n".join(record.getMessage() for record in caplog.records)
        assert BANNER in output
        assert "Scenario Generation" in output
        assert "task_id: task-1" in output
        assert "Decision\n--------\nGenerated 6 scenarios." in output
        assert re.search(r"Scenario Generation completed in \d+\.\d{2} seconds\.", output)

    def test_failed_stage_logs_error_with_duration(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        logger = get_logger(__name__)
        with caplog.at_level(logging.INFO):
            with pytest.raises(RuntimeError):
                with stage_log(logger, "test_code_generation"):
                    raise RuntimeError("strategy unavailable")

        output = "\n".join(record.getMessage() for record in caplog.records)
        assert re.search(
            r"Test Code Generation FAILED after \d+\.\d{2} seconds: "
            r"RuntimeError: strategy unavailable",
            output,
        )


class TestLoggingStandardEnforcement:
    def test_no_module_bypasses_get_logger(self) -> None:
        offenders = [
            str(path.relative_to(PACKAGE_ROOT))
            for path in _package_modules()
            if path != LOGGING_UTIL
            and "logging.getLogger(" in path.read_text(encoding="utf-8")
        ]
        assert offenders == [], (
            "modules must use `from worktop.api_agent.utils.logging import "
            f"get_logger`; direct logging.getLogger found in: {offenders}"
        )

    def test_no_print_statements(self) -> None:
        pattern = re.compile(r"(?<![\w.])print\(")
        offenders = [
            str(path.relative_to(PACKAGE_ROOT))
            for path in _package_modules()
            if pattern.search(path.read_text(encoding="utf-8"))
        ]
        assert offenders == [], f"print() is not allowed; found in: {offenders}"

    def test_no_ad_hoc_logging_configuration(self) -> None:
        offenders = [
            str(path.relative_to(PACKAGE_ROOT))
            for path in _package_modules()
            if path != LOGGING_UTIL
            and "logging.basicConfig(" in path.read_text(encoding="utf-8")
        ]
        assert offenders == [], f"ad-hoc logging config found in: {offenders}"

    def test_all_internal_imports_use_worktop_namespace(self) -> None:
        pattern = re.compile(r"^\s*(from|import)\s+app\b", re.M)
        offenders = [
            str(path.relative_to(PACKAGE_ROOT))
            for path in _package_modules()
            if pattern.search(path.read_text(encoding="utf-8"))
        ]
        assert offenders == [], (
            f"imports must start with worktop.api_agent; bare app.* found in: {offenders}"
        )
