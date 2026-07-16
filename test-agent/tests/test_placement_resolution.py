"""Spec placement: structural validation and bounded feedback retry."""

from pathlib import Path
from types import SimpleNamespace

from worktop.test_agent.app.schemas.generation_request import GenerationRequest
from worktop.test_agent.app.schemas.spec_placement import SpecPlacementDecision
from worktop.test_agent.app.services.generation_orchestrator import (
    GenerationOrchestrator,
)


SPEC = """import { test, expect } from '@playwright/test';

test.describe('plans', () => {
  test('opens a plan', async ({ page }) => {
    await expect(page).toHaveURL(/plans/);
  });
});
"""


def _orchestrator() -> GenerationOrchestrator:
    return GenerationOrchestrator.__new__(GenerationOrchestrator)


def _request(tmp_path: Path) -> GenerationRequest:
    return GenerationRequest(
        job_id="job-1", repo_path=str(tmp_path), test_case_name="case"
    )


def _placement(target: str, create_new: bool = False) -> SpecPlacementDecision:
    return SpecPlacementDecision(
        target_spec_file=target, create_new=create_new, confidence=0.9
    )


def _write_spec(tmp_path: Path, content: str = SPEC) -> str:
    path = tmp_path / "tests" / "plans.spec.ts"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "tests/plans.spec.ts"


def test_validate_placement_flags_missing_target(tmp_path: Path) -> None:
    reason = _orchestrator()._validate_placement(
        _placement("tests/missing.spec.ts"), str(tmp_path)
    )
    assert reason is not None
    assert "does not exist" in reason


def test_validate_placement_accepts_existing_spec(tmp_path: Path) -> None:
    target = _write_spec(tmp_path)
    assert _orchestrator()._validate_placement(_placement(target), str(tmp_path)) is None


def test_validate_placement_flags_empty_spec(tmp_path: Path) -> None:
    target = _write_spec(tmp_path, "// no tests here yet\n")
    reason = _orchestrator()._validate_placement(_placement(target), str(tmp_path))
    assert reason is not None
    assert "no tests or describe blocks" in reason


def test_validate_placement_flags_create_over_existing(tmp_path: Path) -> None:
    target = _write_spec(tmp_path)
    reason = _orchestrator()._validate_placement(
        _placement(target, create_new=True), str(tmp_path)
    )
    assert reason is not None
    assert "already exists" in reason


def test_validate_placement_accepts_fresh_create(tmp_path: Path) -> None:
    assert (
        _orchestrator()._validate_placement(
            _placement("tests/brand-new.spec.ts", create_new=True), str(tmp_path)
        )
        is None
    )


class _RecordingPlacementService:
    def __init__(self, decisions: list[SpecPlacementDecision]) -> None:
        self.decisions = list(decisions)
        self.feedback_history: list[str | None] = []

    def decide(self, inventory, intent=None, ui_context=None, feedback=None):
        self.feedback_history.append(feedback)
        return self.decisions.pop(0)


def _inventory(*paths: str):
    return SimpleNamespace(
        test_files=[SimpleNamespace(path=path) for path in paths]
    )


def _profile(requires_bootstrap: bool = False):
    return SimpleNamespace(requires_bootstrap=requires_bootstrap)


def test_placement_retry_recovers_with_feedback(tmp_path: Path) -> None:
    target = _write_spec(tmp_path)
    service = _RecordingPlacementService(
        [_placement("tests/hallucinated.spec.ts"), _placement(target)]
    )

    placement = _orchestrator()._decide_placement_with_retry(
        _request(tmp_path),
        service,
        _inventory(target),
        None,
        None,
        _profile(),
        [],
    )

    assert placement.target_spec_file == target
    assert len(service.feedback_history) == 2
    assert service.feedback_history[0] is None
    feedback = service.feedback_history[1]
    assert "failed structural validation" in feedback
    assert target in feedback


def test_placement_retry_exhaustion_keeps_original_and_flags_review(
    tmp_path: Path,
) -> None:
    original = _placement("tests/hallucinated.spec.ts")
    service = _RecordingPlacementService(
        [original, _placement("tests/still-wrong.spec.ts")]
    )
    review_reasons: list[str] = []

    placement = _orchestrator()._decide_placement_with_retry(
        _request(tmp_path),
        service,
        _inventory(),
        None,
        None,
        _profile(),
        review_reasons,
    )

    assert placement is original
    assert len(review_reasons) == 1
    assert "could not be structurally validated" in review_reasons[0]


def test_second_placement_feedback_contains_prior_attempt_history(
    tmp_path: Path, monkeypatch
) -> None:
    from worktop.test_agent.app.config import settings

    monkeypatch.setattr(settings, "placement_resolution_agent_retries", 2)
    service = _RecordingPlacementService(
        [
            _placement("tests/first-wrong.spec.ts"),
            _placement("tests/second-wrong.spec.ts"),
            _placement("tests/third-wrong.spec.ts"),
        ]
    )

    _orchestrator()._decide_placement_with_retry(
        _request(tmp_path),
        service,
        _inventory(),
        None,
        None,
        _profile(),
        [],
    )

    assert len(service.feedback_history) == 3
    second_feedback = service.feedback_history[2]
    assert "Previous attempts" in second_feedback
    assert "tests/first-wrong.spec.ts" in second_feedback
    assert "tests/second-wrong.spec.ts" in second_feedback
    assert "Attempt 2" in second_feedback


def test_placement_validation_skipped_for_bootstrap(tmp_path: Path) -> None:
    service = _RecordingPlacementService(
        [_placement("tests/not-created-yet.spec.ts")]
    )
    profile = SimpleNamespace(
        requires_bootstrap=True, playwright_config_files=[], test_dirs=[]
    )

    placement = _orchestrator()._decide_placement_with_retry(
        _request(tmp_path),
        service,
        _inventory(),
        None,
        None,
        profile,
        [],
    )

    assert placement.create_new is True
    assert len(service.feedback_history) == 1
    assert service.feedback_history[0] is None


def test_placement_no_retry_when_valid(tmp_path: Path) -> None:
    target = _write_spec(tmp_path)
    service = _RecordingPlacementService([_placement(target)])

    placement = _orchestrator()._decide_placement_with_retry(
        _request(tmp_path),
        service,
        _inventory(target),
        None,
        None,
        _profile(),
        [],
    )

    assert placement.target_spec_file == target
    assert service.feedback_history == [None]
