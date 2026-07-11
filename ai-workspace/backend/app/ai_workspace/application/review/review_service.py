from typing import Any

from app.ai_workspace.application.tools.apply_patch_tool import ApplyPatchTool
from app.ai_workspace.application.tools.base_tool import ToolExecutionContext
from app.ai_workspace.domain.file_change import FileChange
from app.ai_workspace.domain.review_decision import ReviewDecision
from app.utils.logging_utils import build_log_context, log_metric, log_step


class ReviewService:
    def __init__(self, review_store: Any, apply_patch_tool: ApplyPatchTool):
        self._review_store = review_store
        self._apply_patch_tool = apply_patch_tool

    def save_proposed_changes(self, run_id: str, changes: list[FileChange]) -> None:
        self._review_store.save_changes(run_id, changes)
        log_metric("ai_workspace_proposed_file_count", len(changes))
        log_step("ai_workspace_review_saved", build_log_context(run_id=run_id, stage="review"))

    def get_changes(self, run_id: str) -> list[FileChange]:
        return self._review_store.get_changes(run_id)

    def set_decision(self, run_id: str, file_id: str, decision: ReviewDecision) -> None:
        self._review_store.update_decision(run_id, file_id, decision)
        log_step(
            "ai_workspace_review_decision_set",
            build_log_context(run_id=run_id, file_id=file_id, stage="review"),
        )

    def apply(self, run_id: str, workspace_path: str, tenant_id: str, kept_file_ids: list[str]) -> list[str]:
        context = ToolExecutionContext(workspace_path=workspace_path, tenant_id=tenant_id)
        result = self._apply_patch_tool.execute(context, {"run_id": run_id, "kept_file_ids": kept_file_ids})
        self._review_store.clear(run_id)
        log_metric("ai_workspace_applied_file_count", len(result["applied_paths"]))
        log_step(
            "ai_workspace_changes_applied",
            build_log_context(run_id=run_id, tenant_id=tenant_id, workspace_path=workspace_path, stage="review"),
        )
        return result["applied_paths"]
