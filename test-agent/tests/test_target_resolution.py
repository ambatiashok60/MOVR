"""Extend-target resolution: re-parse recovery and bounded agent retry."""

from pathlib import Path
from types import SimpleNamespace

from worktop.test_agent.app.schemas.behavioral_test_unit import BehavioralTestUnit
from worktop.test_agent.app.schemas.spec_placement import SpecPlacementDecision
from worktop.test_agent.app.schemas.test_action_decision import (
    TestActionDecision as ActionDecision,
    TestActions as Actions,
)
from worktop.test_agent.app.services.generation_orchestrator import (
    GenerationOrchestrator,
)
from worktop.test_agent.app.services.test_action_service import (
    TestActionService as ActionService,
)


SPEC = """import { test, expect } from '@playwright/test';

test.describe('soh table', () => {
  test('toggle sent-to-carrier checkbox flips the value', async ({ page }) => {
    await expect(page).toHaveURL(/soh/);
    await page.getByRole('checkbox').click();
  });

  test('filters rows by carrier', async ({ page }) => {
    await expect(page).toHaveURL(/soh/);
  });
});
"""


def _orchestrator() -> GenerationOrchestrator:
    return GenerationOrchestrator.__new__(GenerationOrchestrator)


def _write_spec(tmp_path: Path, content: str = SPEC) -> str:
    path = tmp_path / "tests" / "soh-table.spec.ts"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "tests/soh-table.spec.ts"


def _extend_decision(**overrides) -> ActionDecision:
    fields = {
        "action": Actions.EXTEND_EXISTING_TEST,
        "target_test_title": "toggle sent-to-carrier checkbox flips the value",
        "target_file_path": "tests/soh-table.spec.ts",
        "target_start_line": 4,
        "confidence": 0.95,
    }
    fields.update(overrides)
    return ActionDecision(**fields)


def test_extension_target_recovered_by_reparse_when_inventory_empty(
    tmp_path: Path,
) -> None:
    spec_file = _write_spec(tmp_path)
    placement = SpecPlacementDecision(target_spec_file=spec_file, confidence=0.9)

    context = _orchestrator()._resolve_existing_test_context(
        placement, _extend_decision(), [], str(tmp_path)
    )

    assert context is not None
    assert context.test_title == "toggle sent-to-carrier checkbox flips the value"
    assert context.file_path == spec_file
    assert context.describe_title == "soh table"
    assert context.start_line <= 4 <= context.end_line


def test_reparse_resolves_line_first(tmp_path: Path) -> None:
    _write_spec(tmp_path)
    decision = _extend_decision(
        target_test_title="a paraphrased title the parser will not match",
        target_start_line=9,
    )

    unit = _orchestrator()._reparse_extension_target(
        decision, str(tmp_path), "tests/soh-table.spec.ts"
    )

    assert unit is not None
    assert unit.test_title == "filters rows by carrier"


def test_reparse_falls_back_to_normalized_title(tmp_path: Path) -> None:
    _write_spec(tmp_path)
    decision = _extend_decision(
        target_test_title="  Toggle Sent-to-Carrier   checkbox flips the value ",
        target_start_line=None,
    )

    unit = _orchestrator()._reparse_extension_target(
        decision, str(tmp_path), "tests/soh-table.spec.ts"
    )

    assert unit is not None
    assert unit.test_title == "toggle sent-to-carrier checkbox flips the value"


def test_reparse_returns_none_when_ambiguous(tmp_path: Path) -> None:
    duplicated = SPEC.replace("filters rows by carrier", "toggle sent-to-carrier checkbox flips the value")
    _write_spec(tmp_path, duplicated)
    decision = _extend_decision(target_start_line=None)

    unit = _orchestrator()._reparse_extension_target(
        decision, str(tmp_path), "tests/soh-table.spec.ts"
    )

    assert unit is None


def test_reparse_disambiguates_duplicate_titles_by_nearest_line(tmp_path: Path) -> None:
    duplicated = SPEC.replace("filters rows by carrier", "toggle sent-to-carrier checkbox flips the value")
    _write_spec(tmp_path, duplicated)
    decision = _extend_decision(target_start_line=99)

    unit = _orchestrator()._reparse_extension_target(
        decision, str(tmp_path), "tests/soh-table.spec.ts"
    )

    assert unit is not None
    assert unit.start_line > 4


def test_bind_selected_test_identity_preserves_agent_discovered_file() -> None:
    service = ActionService.__new__(ActionService)
    ranked = [
        BehavioralTestUnit(
            file_path="tests/other.spec.ts",
            test_title="shared title",
            start_line=5,
            end_line=9,
        )
    ]
    decision = _extend_decision(
        target_test_title="shared title",
        target_file_path="tests/agent-discovered.spec.ts",
        target_start_line=42,
    )

    bound = service._bind_selected_test_identity(decision, ranked)

    assert bound.target_file_path == "tests/agent-discovered.spec.ts"
    assert bound.target_start_line == 42


def test_bind_selected_test_identity_rebinds_when_agent_gave_no_file() -> None:
    service = ActionService.__new__(ActionService)
    ranked = [
        BehavioralTestUnit(
            file_path="tests/other.spec.ts",
            test_title="shared title",
            start_line=5,
            end_line=9,
        )
    ]
    decision = _extend_decision(
        target_test_title="shared title",
        target_file_path=None,
        target_start_line=None,
    )

    bound = service._bind_selected_test_identity(decision, ranked)

    assert bound.target_file_path == "tests/other.spec.ts"
    assert bound.target_start_line == 5


class _RecordingTestActionService:
    def __init__(self, decisions: list[ActionDecision]) -> None:
        self.decisions = list(decisions)
        self.feedback_history: list[str | None] = []

    def decide(self, placement, candidates, intent=None, ui_context=None, repo_path=None, feedback=None):
        self.feedback_history.append(feedback)
        return self.decisions.pop(0)


def _retry_args(tmp_path: Path, action: ActionDecision, stub) -> dict:
    spec_file = "tests/soh-table.spec.ts"
    return {
        "request": SimpleNamespace(repo_path=str(tmp_path)),
        "placement": SpecPlacementDecision(target_spec_file=spec_file, confidence=0.9),
        "action": action,
        "target_behavior": [],
        "test_action": stub,
        "intent": None,
        "ui_context": None,
        "review_reasons": [],
    }


def test_retry_invokes_decision_agent_once_with_feedback(tmp_path: Path) -> None:
    _write_spec(tmp_path)
    unresolvable = _extend_decision(
        target_test_title="a test that does not exist anywhere",
        target_start_line=None,
    )
    corrected = _extend_decision()
    stub = _RecordingTestActionService([corrected])

    action, context = _orchestrator()._resolve_extension_target_with_retry(
        **_retry_args(tmp_path, unresolvable, stub)
    )

    assert len(stub.feedback_history) == 1
    feedback = stub.feedback_history[0]
    assert "could not be structurally resolved" in feedback
    assert "toggle sent-to-carrier checkbox flips the value" in feedback
    assert "filters rows by carrier" in feedback
    assert action.action == Actions.EXTEND_EXISTING_TEST
    assert context is not None
    assert context.test_title == "toggle sent-to-carrier checkbox flips the value"


def test_retry_exhaustion_keeps_action_for_reasoned_downgrade(tmp_path: Path) -> None:
    _write_spec(tmp_path)
    unresolvable = _extend_decision(
        target_test_title="a test that does not exist anywhere",
        target_start_line=None,
    )
    stub = _RecordingTestActionService([unresolvable])

    action, context = _orchestrator()._resolve_extension_target_with_retry(
        **_retry_args(tmp_path, unresolvable, stub)
    )

    assert len(stub.feedback_history) == 1
    assert context is None
    assert action.action == Actions.EXTEND_EXISTING_TEST

    downgraded = _orchestrator()._ensure_safe_extension_action(
        action, context, reason="existing_test_resolution_failed_after_retry"
    )
    assert downgraded.action == Actions.APPEND_NEW_TEST
    assert any(
        "existing_test_resolution_failed_after_retry" in evidence
        for evidence in downgraded.decision_trace.evidence
    )


def test_second_retry_feedback_contains_prior_attempt_history(
    tmp_path: Path, monkeypatch
) -> None:
    from worktop.test_agent.app.config import settings

    monkeypatch.setattr(settings, "extension_resolution_agent_retries", 2)
    _write_spec(tmp_path)
    first_bad = _extend_decision(
        target_test_title="first hallucinated test",
        target_start_line=None,
    )
    second_bad = _extend_decision(
        target_test_title="second hallucinated test",
        target_start_line=None,
    )
    stub = _RecordingTestActionService([second_bad, second_bad])

    _orchestrator()._resolve_extension_target_with_retry(
        **_retry_args(tmp_path, first_bad, stub)
    )

    assert len(stub.feedback_history) == 2
    first_feedback, second_feedback = stub.feedback_history
    assert "first hallucinated test" in first_feedback
    assert "Previous attempts" in first_feedback
    assert "first hallucinated test" in second_feedback
    assert "second hallucinated test" in second_feedback
    assert "Attempt 2" in second_feedback


def test_retry_skipped_for_non_extend_actions(tmp_path: Path) -> None:
    _write_spec(tmp_path)
    append_action = ActionDecision(
        action=Actions.APPEND_NEW_TEST, confidence=0.9
    )
    stub = _RecordingTestActionService([])

    action, context = _orchestrator()._resolve_extension_target_with_retry(
        **_retry_args(tmp_path, append_action, stub)
    )

    assert stub.feedback_history == []
    assert action is append_action
    assert context is None


def test_retry_skipped_when_first_resolution_succeeds(tmp_path: Path) -> None:
    _write_spec(tmp_path)
    stub = _RecordingTestActionService([])

    action, context = _orchestrator()._resolve_extension_target_with_retry(
        **_retry_args(tmp_path, _extend_decision(), stub)
    )

    assert stub.feedback_history == []
    assert action.action == Actions.EXTEND_EXISTING_TEST
    assert context is not None
