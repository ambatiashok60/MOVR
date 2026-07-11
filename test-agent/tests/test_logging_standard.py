from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

from worktop.test_agent.utils.logging import (
    BANNER,
    LOG_FORMAT,
    get_logger,
    stage_log,
)

PACKAGE_ROOT = Path(__file__).parent.parent / "worktop" / "test_agent"
LOGGING_UTIL = PACKAGE_ROOT / "utils" / "logging.py"


def _package_modules() -> list[Path]:
    return [
        path
        for path in PACKAGE_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


class TestGetLogger:
    def test_get_logger_returns_module_named_logger(self) -> None:
        logger = get_logger("worktop.test_agent.app.services.some_service")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "worktop.test_agent.app.services.some_service"

    def test_get_logger_configures_root_formatting(self) -> None:
        get_logger(__name__)

        root = logging.getLogger()
        assert root.handlers, "root logger must have a handler after get_logger()"
        assert "%(filename)s" in LOG_FORMAT
        assert "%(lineno)d" in LOG_FORMAT
        assert "%(funcName)s" in LOG_FORMAT
        assert "%(name)s" in LOG_FORMAT


class TestStageLogFormat:
    def test_stage_renders_banner_summary_decision_and_duration(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        logger = get_logger(__name__)
        with caplog.at_level(logging.INFO):
            with stage_log(logger, "repository_analysis", job_id="job-1") as log:
                log.section("Best Candidate", "renders SOH records")
                log.decision(
                    "Reuse existing executable flow.",
                    reasoning="82% flow overlap with the selected candidate.",
                )

        output = "\n".join(record.getMessage() for record in caplog.records)
        assert BANNER in output
        assert "Repository Analysis" in output
        assert "Starting repository analysis..." in output
        assert "job_id: job-1" in output
        assert "Best Candidate\n--------------\nrenders SOH records" in output
        assert "Decision\n--------\nReuse existing executable flow." in output
        assert "Reasoning: 82% flow overlap" in output
        assert re.search(r"Repository Analysis completed in \d+\.\d{2} seconds\.", output)

    def test_failed_stage_logs_error_with_duration(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        logger = get_logger(__name__)
        with caplog.at_level(logging.INFO):
            with pytest.raises(ValueError):
                with stage_log(logger, "patch_write"):
                    raise ValueError("range outside file")

        output = "\n".join(record.getMessage() for record in caplog.records)
        assert re.search(
            r"Patch Write FAILED after \d+\.\d{2} seconds: ValueError: range outside file",
            output,
        )
        assert any(record.levelno == logging.ERROR for record in caplog.records)


class TestLoggingStandardEnforcement:
    """The coding standard is enforced by scanning the package source."""

    def test_no_module_bypasses_get_logger(self) -> None:
        offenders = [
            str(path.relative_to(PACKAGE_ROOT))
            for path in _package_modules()
            if path != LOGGING_UTIL
            and "logging.getLogger(" in path.read_text(encoding="utf-8")
        ]
        assert offenders == [], (
            "modules must use `from worktop.test_agent.utils.logging import "
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
            f"imports must start with worktop.test_agent; bare app.* found in: {offenders}"
        )
