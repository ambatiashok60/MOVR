from __future__ import annotations

import subprocess

from app.config import settings
from app.schemas.generated_file import GeneratedFile
from app.schemas.repo_profile import RepoProfile
from app.schemas.validation_result import ValidationResult
from app.validation.validation_command_resolver import ValidationCommandResolver


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
        return self._execute(command, profile.repo_path, details)

    def _execute(
        self,
        command: str,
        repo_path: str,
        details: list[str],
    ) -> ValidationResult:
        try:
            completed = subprocess.run(
                command,
                shell=True,
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
