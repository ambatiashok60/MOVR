"""Writer failures become repair-loop feedback instead of killing the job."""

import pytest

from worktop.test_agent.app.schemas.code_patch import (
    CodePatch,
    PatchSet,
    PatchWriteResult,
)
from worktop.test_agent.app.schemas.generation_request import GenerationRequest
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.validation_result import (
    ValidationCheck,
    ValidationResult,
)
from worktop.test_agent.app.services.generation_orchestrator import (
    GenerationOrchestrator,
)


class _StubAdapter:
    def __init__(self, write_errors: list[Exception | None]) -> None:
        self.write_errors = list(write_errors)
        self.apply_calls = 0
        self.rollback_calls: list[PatchWriteResult] = []

    def apply_patch(self, repo_path: str, patches: PatchSet) -> PatchWriteResult:
        self.apply_calls += 1
        error = self.write_errors.pop(0) if self.write_errors else None
        if error is not None:
            raise error
        return PatchWriteResult()

    def rollback(self, repo_path: str, result: PatchWriteResult) -> None:
        self.rollback_calls.append(result)

    def validate(self, repo_path, patches, ui_context) -> ValidationResult:
        return ValidationResult(
            passed=True,
            checks=[ValidationCheck(name="stub", passed=True, output="ok")],
        )


class _StubRepair:
    def __init__(self) -> None:
        self.received: list[ValidationResult] = []
        self.histories: list[list[str]] = []

    def repair(
        self, patches, validation, anchor=None, locators=None, history=None
    ) -> PatchSet:
        self.received.append(validation)
        self.histories.append(list(history or []))
        return patches


class _StubCritic:
    def review(self, patches, ui_context=None, anchor=None, locators=None) -> PatchSet:
        return patches


def _orchestrator(adapter: _StubAdapter) -> GenerationOrchestrator:
    orch = GenerationOrchestrator.__new__(GenerationOrchestrator)
    orch.adapters = None
    orch.adapter = adapter
    orch._validate_patch_plan = lambda *args, **kwargs: ValidationResult(
        passed=True,
        checks=[ValidationCheck(name="plan_stub", passed=True, output="ok")],
    )
    return orch


def _request(run_validation: bool = True) -> GenerationRequest:
    return GenerationRequest(
        job_id="job-1",
        repo_path="/tmp/repo",
        test_case_name="case",
        run_validation=run_validation,
    )


def _patches() -> PatchSet:
    return PatchSet(
        patches=[
            CodePatch(
                path="tests/plans.spec.ts",
                operation="append",
                content="test('x', async () => {});",
            )
        ]
    )


def _run(orch, request, repair, critic):
    return orch._write_validate_and_repair(
        request,
        _patches(),
        PlaywrightUiContext(),
        None,
        critic,
        repair,
    )


def test_write_failure_enters_repair_loop_and_recovers() -> None:
    adapter = _StubAdapter(
        [ValueError("Generated test title already exists in tests/plans.spec.ts: x")]
    )
    repair = _StubRepair()
    orch = _orchestrator(adapter)

    result, validation, _ = _run(orch, _request(), repair, _StubCritic())

    assert adapter.apply_calls == 2
    assert len(repair.received) == 1
    failed = repair.received[0]
    failed_names = [check.name for check in failed.checks if not check.passed]
    assert failed_names == ["patch_write"]
    assert "already exists" in failed.checks[0].output
    assert validation is not None and validation.passed


def test_write_failure_repairs_even_when_validation_disabled() -> None:
    adapter = _StubAdapter([ValueError("structural_outcome: broken")])
    repair = _StubRepair()
    orch = _orchestrator(adapter)

    result, validation, _ = _run(orch, _request(run_validation=False), repair, _StubCritic())

    assert adapter.apply_calls == 2
    assert len(repair.received) == 1
    assert validation is None


def test_write_failure_exhaustion_returns_failed_patch_write_check() -> None:
    adapter = _StubAdapter([ValueError("always broken")] * 10)
    repair = _StubRepair()
    orch = _orchestrator(adapter)

    result, validation, _ = _run(orch, _request(), repair, _StubCritic())

    assert validation is not None and not validation.passed
    assert [check.name for check in validation.checks] == ["patch_write"]
    assert result.applied == []
    assert all(rolled.applied == [] for rolled in adapter.rollback_calls)


def test_repair_receives_accumulated_failure_history() -> None:
    adapter = _StubAdapter([ValueError("always broken")] * 10)
    repair = _StubRepair()
    orch = _orchestrator(adapter)

    _run(orch, _request(), repair, _StubCritic())

    assert len(repair.histories) >= 2
    assert repair.histories[0] == []
    assert any("always broken" in entry for entry in repair.histories[1])
    assert len(repair.histories[1]) == 1


def test_non_value_errors_still_propagate() -> None:
    adapter = _StubAdapter([OSError("disk full")])
    orch = _orchestrator(adapter)

    with pytest.raises(OSError, match="disk full"):
        _run(orch, _request(), _StubRepair(), _StubCritic())
