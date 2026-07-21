"""Runs fast, targeted validation on the files an agent run changed.

Deliberately avoids running full test suites for tiny changes. Python files get
a syntax compile; JSON gets parsed; other kinds are reported as skipped. This
keeps validation quick and safe for the local preview while still exercising the
whole validation -> SSE -> UI path.
"""

from __future__ import annotations

import json
import py_compile
import time
from pathlib import Path

from app.models.changes import ValidationResult
from app.validation.command_detector import validation_kind
from app.workspace.path_guard import PathGuard


class ValidationManager:
    def __init__(self) -> None:
        self._path_guard = PathGuard()

    def validate(self, workspace: Path, changed_paths: list[str]) -> list[ValidationResult]:
        if not changed_paths:
            return [ValidationResult(name="targeted validation", status="skipped",
                                     summary="No changed files to validate")]
        results: list[ValidationResult] = []
        for rel in changed_paths:
            kind = validation_kind(rel)
            if kind is None:
                results.append(ValidationResult(name=rel, status="skipped",
                                                summary="No applicable validation"))
                continue
            results.append(self._run_one(workspace, rel, kind))
        return results

    def _run_one(self, workspace: Path, rel: str, kind: str) -> ValidationResult:
        started = time.perf_counter()
        try:
            target = self._path_guard.resolve_inside_workspace(workspace, rel)
        except PermissionError as exc:
            return ValidationResult(name=rel, status="failed", summary=str(exc))

        if not target.exists():
            return ValidationResult(name=rel, status="skipped", summary="File no longer present")

        if kind == "python_syntax":
            return self._python_syntax(target, rel, started)
        if kind == "json":
            return self._json_valid(target, rel, started)
        # typescript etc. need the toolchain; report skipped rather than block.
        return ValidationResult(name=f"{kind}:{rel}", status="skipped",
                                summary="Toolchain validation left to CI",
                                duration_ms=self._ms(started))

    def _python_syntax(self, target: Path, rel: str, started: float) -> ValidationResult:
        try:
            py_compile.compile(str(target), doraise=True)
            return ValidationResult(name=f"python syntax: {rel}", status="passed",
                                    exit_code=0, summary="Compiles cleanly", duration_ms=self._ms(started))
        except py_compile.PyCompileError as exc:
            return ValidationResult(name=f"python syntax: {rel}", status="failed", exit_code=1,
                                    summary="Syntax error", output_excerpt=str(exc)[:500],
                                    duration_ms=self._ms(started))

    def _json_valid(self, target: Path, rel: str, started: float) -> ValidationResult:
        try:
            json.loads(target.read_text(encoding="utf-8"))
            return ValidationResult(name=f"json: {rel}", status="passed", exit_code=0,
                                    summary="Valid JSON", duration_ms=self._ms(started))
        except (json.JSONDecodeError, OSError) as exc:
            return ValidationResult(name=f"json: {rel}", status="failed", exit_code=1,
                                    summary="Invalid JSON", output_excerpt=str(exc)[:500],
                                    duration_ms=self._ms(started))

    @staticmethod
    def _ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
