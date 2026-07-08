from typing import Any

from app.ai_workspace.application.tools.base_tool import BaseTool, ToolExecutionContext
from app.ai_workspace.domain.review_decision import ReviewDecision
from app.ai_workspace.domain.tool_definition import ToolCapabilities, ToolDefinition
from app.repository.application.file_write_service import FileWriteService


class ApplyPatchTool(BaseTool):
    """Writes exactly the file changes a user has marked 'kept' for a given run — this is the
    only tool review_service.py's apply flow invokes, and it is never exposed to the LLM as a
    callable tool (it's driven by review_routes.py -> review_service.py, not by a model tool
    call). It's modeled as a BaseTool anyway for consistency with the rest of the tool
    execution path (ToolExecutionContext, same execute() signature)."""

    def __init__(self, review_store: Any, file_write_service: FileWriteService):
        self._review_store = review_store
        self._file_write_service = file_write_service

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
        applied_paths: list[str] = []

        for change in self._review_store.get_changes(run_id):
            if change.id not in kept_file_ids:
                continue
            self._file_write_service.write(context.workspace_path, change.file_path, change.new_content)
            change.decision = ReviewDecision.KEPT
            applied_paths.append(change.file_path)

        return {"applied_paths": applied_paths}
