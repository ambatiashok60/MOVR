from __future__ import annotations

import subprocess

from app.config import settings

import logging


from app.schemas.code_patch import PatchSet
from app.schemas.playwright_ui_context import PlaywrightUiContext
from app.schemas.validation_result import ValidationCheck, ValidationResult
from app.validation.playwright_validator import PlaywrightValidator
from app.validation.playwright_ui_quality_validator import PlaywrightUiQualityValidator
from app.validation.syntax_validator import SyntaxValidator

logger = logging.getLogger(__name__)


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
                self._execution_check(repo_path, patches, ui_context),
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

    def _execution_check(
        self,
        repo_path: str,
        patches: PatchSet | None,
        ui_context: PlaywrightUiContext | None,
    ) -> ValidationCheck:
        """Env-gated run-until-green: actually execute the changed specs so the
        repair loop converges on a passing run, not just static checks."""
        if not settings.enable_targeted_runtime:
            return ValidationCheck(
                name="targeted_execution",
                passed=True,
                output="Targeted execution disabled (enable_targeted_runtime=false).",
            )
        commands = [c.command for c in (ui_context.ci_commands if ui_context else []) if "playwright" in c.command]
        changed_specs = [
            p.path for p in (patches.patches if patches else [])
            if p.path.endswith((".spec.ts", ".e2e.ts", ".pw.ts", ".playwright.ts"))
        ]
        if not commands or not changed_specs:
            return ValidationCheck(
                name="targeted_execution",
                passed=True,
                output="No Playwright command or changed specs to execute.",
            )
        command = f"{commands[0]} {' '.join(changed_specs)}"
        try:
            completed = subprocess.run(
                command, shell=True, cwd=repo_path, capture_output=True,
                text=True, timeout=settings.validation_timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return ValidationCheck(
                name="targeted_execution", passed=False,
                output=f"{command}\nTimed out after {settings.validation_timeout_seconds}s",
            )
        except OSError as exc:
            return ValidationCheck(
                name="targeted_execution", passed=False, output=f"{command}\n{exc}"
            )
        tail = (completed.stdout + "\n" + completed.stderr)[-6000:]
        return ValidationCheck(
            name="targeted_execution",
            passed=completed.returncode == 0,
            output=f"{command}\nexit code: {completed.returncode}\n{tail.strip()}",
        )
