from __future__ import annotations

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
        return ValidationResult(
            passed=False,
            command=command,
            summary="Command execution is not enabled yet",
            details=details,
        )
