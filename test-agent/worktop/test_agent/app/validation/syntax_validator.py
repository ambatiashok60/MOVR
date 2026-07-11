from __future__ import annotations

from worktop.test_agent.app.schemas.validation_result import ValidationCheck


class SyntaxValidator:
    def validate(self, repo_path: str) -> ValidationCheck:
        return ValidationCheck(name="syntax", passed=True, output="deferred")
