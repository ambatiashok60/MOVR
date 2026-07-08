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

from app.schemas.behavioral_test_unit import BehavioralTestUnit
from app.schemas.repository_inventory import RepositoryInventory
from app.tools.playwright_parser_tool import PlaywrightParserTool


class BehavioralInventoryService:
    def __init__(self) -> None:
        self.parser = PlaywrightParserTool()

    @log_performance("behavioral_inventory_service.extract")
    def extract(self, inventory: RepositoryInventory) -> list[BehavioralTestUnit]:
        log_step("behavioral_inventory_started", {"repo_head": inventory.repo_head})
        try:
            units: list[BehavioralTestUnit] = []
            root = Path(inventory.repo_path)
            for test_file in inventory.test_files:
                if not test_file.is_e2e_candidate:
                    continue
                path = root / test_file.path
                if not path.exists():
                    continue
                content = path.read_text(encoding="utf-8", errors="ignore")
                units.extend(self.parser.extract_tests(test_file.path, content))
            log_metric("behavioral_units_count", len(units))
            logger.info("Behavioral inventory extracted")
            return units
        except Exception as exc:
            log_exception(exc, context={"stage": "behavioral_inventory"})
            raise
