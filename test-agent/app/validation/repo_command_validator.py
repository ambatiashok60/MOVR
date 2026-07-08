from __future__ import annotations

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

from app.schemas.validation_result import ValidationResult
from app.validation.playwright_validator import PlaywrightValidator
from app.validation.syntax_validator import SyntaxValidator


class RepoCommandValidator:
    def __init__(self) -> None:
        self.syntax = SyntaxValidator()
        self.playwright = PlaywrightValidator()

    @log_performance("repo_command_validator.validate")
    def validate(self, repo_path: str) -> ValidationResult:
        log_step("repo_validation_started", {"repo_path": repo_path})
        try:
            checks = [
                self.syntax.validate(repo_path),
                self.playwright.validate(repo_path),
            ]
            passed = all(check.passed for check in checks)
            log_metric("validation_check_count", len(checks))
            logger.info("Repository validation completed")
            return ValidationResult(passed=passed, checks=checks)
        except Exception as exc:
            log_exception(exc, context={"repo_path": repo_path, "stage": "validation"})
            raise
