from __future__ import annotations

from app.schemas.validation_result import ValidationCheck


class SyntaxValidator:
    def validate(self, repo_path: str) -> ValidationCheck:
        return ValidationCheck(name="syntax", passed=True, output="deferred")
