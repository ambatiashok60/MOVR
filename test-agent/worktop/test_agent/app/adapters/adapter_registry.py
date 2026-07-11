from __future__ import annotations

import logging

from worktop.test_agent.app.adapters.playwright_adapter import PlaywrightAdapter
from worktop.test_agent.app.adapters.technology_adapter import TechnologyAdapter
from worktop.test_agent.app.logging_config import log_event
from worktop.test_agent.utils.logging import get_logger

logger = get_logger(__name__)


class UnknownTechnologyError(ValueError):
    def __init__(self, technology: str, registered: list[str]) -> None:
        super().__init__(
            f"No technology adapter registered for '{technology}'; "
            f"registered adapters: {', '.join(registered) or 'none'}."
        )


class AdapterRegistry:
    """Resolve the technology adapter the core engine should drive.

    New stacks plug in through `register` without touching the orchestration.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, TechnologyAdapter] = {}

    def register(self, adapter: TechnologyAdapter) -> None:
        self._adapters[adapter.technology] = adapter
        log_event(
            logger,
            logging.INFO,
            "adapter_registry",
            "registered",
            technology=adapter.technology,
            adapter=type(adapter).__name__,
        )

    def resolve(self, technology: str) -> TechnologyAdapter:
        adapter = self._adapters.get(technology)
        if adapter is None:
            raise UnknownTechnologyError(technology, sorted(self._adapters))
        return adapter

    def registered(self) -> list[str]:
        return sorted(self._adapters)


def default_adapter_registry() -> AdapterRegistry:
    registry = AdapterRegistry()
    registry.register(PlaywrightAdapter())
    return registry
