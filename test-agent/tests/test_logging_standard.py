from __future__ import annotations

import logging
import re
from pathlib import Path

from worktop.core_services.app.utility.custom_logger.logging import logger

PACKAGE_ROOT = Path(__file__).parent.parent / "worktop" / "test_agent"


def _package_modules() -> list[Path]:
    return [
        path
        for path in PACKAGE_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


class TestCustomLogger:
    def test_worktop_logger_is_available(self) -> None:
        assert isinstance(logger, logging.Logger)


class TestLoggingStandardEnforcement:
    """The coding standard is enforced by scanning the package source."""

    def test_all_application_modules_import_worktop_custom_logger(self) -> None:
        expected = (
            "from worktop.core_services.app.utility.custom_logger.logging "
            "import logger"
        )
        offenders = [
            str(path.relative_to(PACKAGE_ROOT))
            for path in _package_modules()
            if path.parent.name not in {"schemas", "prompts"}
            and "logger." in path.read_text(encoding="utf-8")
            and expected not in path.read_text(encoding="utf-8")
        ]
        assert offenders == [], (
            "logging modules must import Worktop's custom logger directly; "
            f"offenders: {offenders}"
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
            if "logging.basicConfig(" in path.read_text(encoding="utf-8")
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
