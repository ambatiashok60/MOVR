from app.ai_workspace.application.agent.agent_service import _parse_json_response, _parse_agent_turn
from app.ai_workspace.application.agent.patch_validation_service import PatchValidationService
from app.ai_workspace.application.review.engineering_review_service import EngineeringReviewService
from app.common.data_governance import DataGovernanceService
from app.llm.application.review_budget_service import ReviewBudgetService
from app.repository.application.workspace_transaction_service import WorkspaceTransactionService, StaleProposalError
from app.repository.application.file_write_service import FileWriteService
from app.repository.infrastructure.local_file_writer import LocalFileWriter
from app.ai_workspace.domain.file_change import FileChange, FileChangeStatus
from app.ai_workspace.domain.review_decision import ReviewDecision
import hashlib
import pytest


def test_agent_plan_parser_extracts_json_from_markdown() -> None:
    payload = _parse_json_response('Plan:\n```json\n{"plan":{"steps":[]},"file_changes":[]}\n```')
    assert payload["plan"]["steps"] == []


def test_repository_governance_blocks_and_redacts() -> None:
    service = DataGovernanceService()
    assert service.release(".env", "API_KEY=real-secret") is None
    released = service.release("src/settings.py", "password=hunter2secret\nname=workspace")
    assert released is not None
    assert "hunter2secret" not in released
    assert "[REDACTED]" in released
    assert service.audit.files_blocked == [".env"]
    assert service.audit.redactions == 1


def test_budget_thresholds_are_review_only() -> None:
    service = ReviewBudgetService(max_llm_calls=1, max_prompt_characters=5, max_seconds=999)
    service.charge("run-1", prompt_chars=10, completion_chars=4)
    service.charge("run-1", prompt_chars=10, completion_chars=4)
    report = service.report("run-1")
    assert report.review_required is True
    assert report.usage.llm_calls == 2
    assert len(report.findings) == 2


def test_evidence_backed_turn_validates_and_scores() -> None:
    turn = _parse_agent_turn('''{
      "status":"ready_to_patch",
      "reasoning_summary":"Routes differ",
      "root_cause":"Frontend omits /agent in the SSE route",
      "evidence":["frontend sse.service.ts route", "backend sse_routes.py route"],
      "tool_calls":[],
      "plan":{"steps":[{"description":"Align route","affected_files":["src/sse.ts"],"confidence":0.9}]},
      "file_changes":[{"path":"src/config.json","status":"modified","new_content":"{\\"route\\":\\"/agent/executions\\"}","rationale":"Align backend","evidence":["route comparison"]}],
      "final_summary":"Aligned the route"
    }''')
    validation = PatchValidationService().validate(turn.file_changes)
    review = EngineeringReviewService().build(turn, validation, observation_count=2)
    assert validation.passed is True
    assert review["quality_score"] >= 80
    assert review["risk_level"] == "low"


def _change(path: str, original: str, new: str) -> FileChange:
    return FileChange(
        id=path, run_id="run-1", file_path=path, status=FileChangeStatus.MODIFIED,
        additions=1, deletions=1, new_content=new, diff_hunks=[],
        decision=ReviewDecision.KEPT,
        original_digest=hashlib.sha256(original.encode()).hexdigest(),
        original_existed=True,
    )


def test_transaction_applies_and_journals(tmp_path) -> None:
    repo = tmp_path / "repo"; repo.mkdir()
    target = repo / "app.py"; target.write_text("old")
    service = WorkspaceTransactionService(str(tmp_path / "tx"), FileWriteService(LocalFileWriter()))
    paths = service.apply("run-1", str(repo), [_change("app.py", "old", "new")])
    assert paths == ["app.py"]
    assert target.read_text() == "new"
    journal = tmp_path / "tx" / "ai-workspace-transactions" / "runs" / "run-1" / "journal.jsonl"
    assert "committed" in journal.read_text()


def test_transaction_rejects_stale_proposal(tmp_path) -> None:
    repo = tmp_path / "repo"; repo.mkdir()
    (repo / "app.py").write_text("changed-by-user")
    service = WorkspaceTransactionService(str(tmp_path / "tx"), FileWriteService(LocalFileWriter()))
    with pytest.raises(StaleProposalError):
        service.apply("run-1", str(repo), [_change("app.py", "old", "agent")])
    assert (repo / "app.py").read_text() == "changed-by-user"
