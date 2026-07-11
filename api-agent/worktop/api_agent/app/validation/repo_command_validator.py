from __future__ import annotations

import shlex
import subprocess

from worktop.api_agent.app.config import settings
from worktop.api_agent.app.schemas.generated_file import GeneratedFile
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.validation_result import ValidationResult
from worktop.api_agent.app.validation.validation_command_resolver import ValidationCommandResolver
from worktop.api_agent.app.utils.logging_utils import log_step


class RepoCommandValidator:
    def __init__(self) -> None:
        self.resolver = ValidationCommandResolver()

    def validate(
        self,
        profile: RepoProfile,
        generated_files: list[GeneratedFile],
        target: str,
        execute: bool = False,
    ) -> ValidationResult:
        commands = self.resolver.resolve(profile, target)
        if not commands:
            return ValidationResult(
                passed=False,
                command=None,
                summary="No repo-native validation command was detected",
                details=["Generation completed, but validation command discovery did not find a command."],
            )
        command = commands[0]
        details = [
            f"Resolved validation command: {command}",
            *[f"Generated file: {file.path}" for file in generated_files],
        ]
        if not execute:
            details.append("Dry-run validation only; command execution is disabled for this scaffold.")
            return ValidationResult(
                passed=True,
                command=command,
                summary="Validation command resolved",
                details=details,
            )
        log_step("api_validation_execution_started", {"command": command, "target": target})
        result = self._execute(command, profile.repo_path, details)
        log_step(
            "api_validation_execution_completed",
            {"command": command, "passed": result.passed, "summary": result.summary},
        )
        return result

    def _execute(
        self,
        command: str,
        repo_path: str,
        details: list[str],
    ) -> ValidationResult:
        try:
            argv = shlex.split(command)
            if not argv or any(token in command for token in (";", "&&", "||", "|", "`", "$(")):
                return ValidationResult(
                    passed=False,
                    command=command,
                    summary="Unsafe validation command rejected",
                    details=[*details, "Shell composition is not allowed for autonomous execution."],
                )
            if argv[0] not in settings.validation_allowed_executables:
                return ValidationResult(
                    passed=False,
                    command=command,
                    summary="Unapproved validation executable rejected",
                    details=[*details, f"Executable `{argv[0]}` is not in the autonomous execution allowlist."],
                )
            completed = subprocess.run(
                argv,
                shell=False,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=settings.execution_timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return ValidationResult(
                passed=False,
                command=command,
                summary="Validation command timed out",
                details=[*details, f"Timed out after {settings.execution_timeout_seconds}s"],
            )
        except OSError as exc:
            return ValidationResult(
                passed=False,
                command=command,
                summary="Validation command could not be executed",
                details=[*details, str(exc)],
            )
        output_tail = (completed.stdout + "\n" + completed.stderr)[-6000:]
        passed = completed.returncode == 0
        return ValidationResult(
            passed=passed,
            command=command,
            summary="Tests executed and passed" if passed else "Test execution failed",
            details=[*details, f"exit code: {completed.returncode}", output_tail.strip()],
        )
