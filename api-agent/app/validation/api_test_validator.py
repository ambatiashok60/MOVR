from __future__ import annotations

from app.schemas.generated_file import GeneratedFile
from app.schemas.repo_profile import RepoProfile
from app.schemas.validation_result import ValidationResult
from app.tools.path_safety import resolve_workspace_path
from app.validation.repo_command_validator import RepoCommandValidator


class ApiTestValidator:
    def __init__(self) -> None:
        self.command_validator = RepoCommandValidator()

    def validate(
        self,
        repo_path: str,
        generated_files: list[GeneratedFile],
        profile: RepoProfile | None = None,
        target: str = "ci",
        execute: bool = False,
    ) -> ValidationResult:
        root = resolve_workspace_path(repo_path)
        missing = [file.path for file in generated_files if not (root / file.path).exists()]
        if missing:
            return ValidationResult(
                passed=False,
                summary="Generated file validation failed",
                details=[f"Missing file: {path}" for path in missing],
            )
        if profile is not None:
            command_result = self.command_validator.validate(
                profile,
                generated_files,
                target=target,
                execute=execute,
            )
            command_result.details = [
                "Generated file existence check passed.",
                *command_result.details,
            ]
            return command_result
        return ValidationResult(
            passed=True,
            summary="Generated files were written successfully",
            details=[f"Found {file.path}" for file in generated_files],
        )
