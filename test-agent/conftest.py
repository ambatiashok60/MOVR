"""Standalone test bootstrap for Worktop-owned infrastructure imports."""

from __future__ import annotations

import logging
import sys
import types


def _install_custom_logger_stub() -> None:
    """Provide Worktop's logger import only when core_services is unavailable."""
    module_name = "worktop.core_services.app.utility.custom_logger.logging"
    try:
        __import__(module_name)
        return
    except ImportError:
        pass

    parents = (
        "worktop.core_services",
        "worktop.core_services.app",
        "worktop.core_services.app.utility",
        "worktop.core_services.app.utility.custom_logger",
    )
    for name in parents:
        sys.modules.setdefault(name, types.ModuleType(name))
    logging_module = types.ModuleType(module_name)
    logging_module.logger = logging.getLogger("worktop.test_agent")
    sys.modules[module_name] = logging_module


_install_custom_logger_stub()
