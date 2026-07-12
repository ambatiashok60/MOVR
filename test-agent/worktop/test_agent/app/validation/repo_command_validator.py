from __future__ import annotations



from worktop.test_agent.app.schemas.code_patch import PatchSet
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.validation_result import ValidationCheck, ValidationResult
from worktop.test_agent.app.validation.playwright_validator import PlaywrightValidator
from worktop.test_agent.app.validation.playwright_ui_quality_validator import PlaywrightUiQualityValidator
from worktop.test_agent.app.validation.syntax_validator import SyntaxValidator
from worktop.core_services.app.utility.custom_logger.logging import logger



class RepoCommandValidator:
    SPEC_SUFFIXES = (
        ".spec.ts",
        ".spec.tsx",
        ".e2e.ts",
        ".e2e.tsx",
        ".test.ts",
        ".test.tsx",
        ".pw.ts",
        ".pw.tsx",
        ".playwright.ts",
        ".playwright.tsx",
    )

    def __init__(self) -> None:
        self.syntax = SyntaxValidator()
        self.playwright = PlaywrightValidator()
        self.ui_quality = PlaywrightUiQualityValidator()

    def validate(
        self,
        repo_path: str,
        patches: PatchSet | None = None,
        ui_context: PlaywrightUiContext | None = None,
    ) -> ValidationResult:
        logger.info(
            "[playwright-generation] stage=repo_validation status=started repo=%s",
            repo_path,
        )
        try:
            checks = [
                self.syntax.validate(repo_path),
                self.playwright.validate(repo_path),
                self.ui_quality.validate(patches, ui_context),
                self._ci_command_check(patches, ui_context),
            ]
            passed = all(check.passed for check in checks)
            logger.info(
                "[playwright-generation] stage=repo_validation status=completed passed=%s checks=%s",
                passed,
                len(checks),
            )
            return ValidationResult(passed=passed, checks=checks)
        except Exception as exc:
            logger.exception(
                "[playwright-generation] stage=repo_validation status=failed repo=%s error=%s",
                repo_path,
                exc,
            )
            raise

    def _ci_command_check(
        self,
        patches: PatchSet | None,
        ui_context: PlaywrightUiContext | None,
    ) -> ValidationCheck:
        commands = [command.command for command in (ui_context.ci_commands if ui_context else [])]
        changed_specs = [
            patch.path
            for patch in (patches.patches if patches else [])
            if patch.path.endswith(self.SPEC_SUFFIXES)
        ]
        if not commands:
            return ValidationCheck(
                name="ci_command_recommendation",
                passed=True,
                output="No CI Playwright command detected; use repository-specific Playwright command.",
            )
        targeted = []
        for command in commands:
            if changed_specs and "playwright" in command:
                targeted.extend(f"{command} {spec}" for spec in changed_specs)
            else:
                targeted.append(command)
        return ValidationCheck(
            name="ci_command_recommendation",
            passed=True,
            output="\n".join(targeted),
        )
