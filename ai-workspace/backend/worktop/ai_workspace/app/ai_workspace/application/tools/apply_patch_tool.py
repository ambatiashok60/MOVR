from typing import Any

from worktop.ai_workspace.app.ai_workspace.application.tools.base_tool import BaseTool, ToolExecutionContext
from worktop.ai_workspace.app.ai_workspace.domain.review_decision import ReviewDecision
from worktop.ai_workspace.app.ai_workspace.domain.file_change import FileChangeStatus
from worktop.ai_workspace.app.ai_workspace.domain.tool_definition import ToolCapabilities, ToolDefinition
from worktop.ai_workspace.app.repository.application.file_write_service import FileWriteService
from worktop.ai_workspace.app.repository.application.workspace_transaction_service import WorkspaceTransactionService


class ApplyPatchTool(BaseTool):
    """Writes exactly the file changes a user has marked 'kept' for a given run — this is the
    only tool review_service.py's apply flow invokes, and it is never exposed to the LLM as a
    callable tool (it's driven by review_routes.py -> review_service.py, not by a model tool
    call). It's modeled as a BaseTool anyway for consistency with the rest of the tool
    execution path (ToolExecutionContext, same execute() signature)."""

    def __init__(self, review_store: Any, file_write_service: FileWriteService, transaction_service: WorkspaceTransactionService | None = None):
        self._review_store = review_store
        self._file_write_service = file_write_service
        self._transactions = transaction_service

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            id="apply_patch",
            name="Apply Patch",
            description="Write the kept file changes from a completed run to disk.",
            capabilities=ToolCapabilities(reads_files=False, writes_files=True, requires_confirmation=True),
            parameters_schema={
                "type": "object",
                "properties": {"run_id": {"type": "string"}, "kept_file_ids": {"type": "array"}},
                "required": ["run_id", "kept_file_ids"],
            },
        )

    def execute(self, context: ToolExecutionContext, arguments: dict) -> dict:
        run_id = arguments["run_id"]
        kept_file_ids = set(arguments["kept_file_ids"])
        changes = [change for change in self._review_store.get_changes(run_id) if change.id in kept_file_ids]
        if self._transactions:
            applied_paths = self._transactions.apply(run_id, context.workspace_path, changes)
        else:
            applied_paths = []
            for change in changes:
                if change.status == FileChangeStatus.DELETED:
                    self._file_write_service.delete(context.workspace_path, change.file_path)
                else:
                    self._file_write_service.write(context.workspace_path, change.file_path, change.new_content)
                applied_paths.append(change.file_path)
        for change in changes:
            change.decision = ReviewDecision.KEPT

        return {"applied_paths": applied_paths}
