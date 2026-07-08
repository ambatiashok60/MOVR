from fastapi import APIRouter, Depends, HTTPException

from app.ai_workspace.application.review.review_service import ReviewService
from app.ai_workspace.domain.execution_context import ExecutionContext
from app.ai_workspace.dto.execution_dto import ExecutionRunDto, ExecutionStageDto
from app.ai_workspace.dto.mappers import execution_to_dto
from app.dependencies.ai_workspace_dependencies import get_execution_by_id, get_plan_by_execution_id, get_review_service

router = APIRouter(prefix="/ai-workspace/agent/executions", tags=["Execution"])


@router.get("/{execution_id}", response_model=ExecutionRunDto)
def get_execution(
    execution: ExecutionContext | None = Depends(get_execution_by_id),
    review_service: ReviewService = Depends(get_review_service),
) -> ExecutionRunDto:
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    file_changes = review_service.get_changes(execution.execution_id)
    return execution_to_dto(execution, file_changes)


@router.get("/{execution_id}/timeline", response_model=list[ExecutionStageDto])
def get_timeline(execution: ExecutionContext | None = Depends(get_execution_by_id)) -> list[ExecutionStageDto]:
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return [ExecutionStageDto(id=s.id, label=s.label, status=s.status.value, detail=s.detail) for s in execution.stages]


@router.get("/{execution_id}/plan")
def get_plan(execution: ExecutionContext | None = Depends(get_execution_by_id)) -> dict:
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    plan = get_plan_by_execution_id(execution.execution_id)
    if plan is not None:
        return {
            "id": f"plan-{plan.execution_id}",
            "executionId": plan.execution_id,
            "steps": [
                {
                    "id": f"{plan.execution_id}-step-{step.order}",
                    "order": step.order,
                    "description": step.description,
                    "status": "done",
                    "affectedFiles": step.affected_files,
                    "toolCalls": [
                        {
                            "toolName": tool_call.tool_name,
                            "arguments": tool_call.arguments,
                        }
                        for tool_call in step.tool_calls
                    ],
                    "confidence": step.confidence,
                }
                for step in plan.steps
            ],
            "overallConfidence": plan.overall_confidence,
        }
    return {
        "id": f"plan-{execution.execution_id}",
        "executionId": execution.execution_id,
        "steps": [
            {
                "id": stage.id,
                "order": index,
                "description": stage.label,
                "status": "done" if stage.status.value == "done" else "in_progress" if stage.status.value == "active" else stage.status.value,
                "affectedFiles": [],
                "toolCalls": [],
            }
            for index, stage in enumerate(execution.stages, start=1)
        ],
    }


@router.post("/{execution_id}/cancel")
def cancel_execution(execution_id: str) -> dict:
    # UNCONFIRMED / not implemented: ExecutionOrchestrator.run() is a single awaited call with
    # no cancellation hook — cancelling mid-run would need the orchestrator to accept a
    # cancellation token and check it between stages, and the LLM call itself would need to be
    # cancellable (unconfirmed whether DefaultLLMClient supports that at all). Returning 501
    # rather than pretending this works.
    raise HTTPException(status_code=501, detail="Execution cancellation is not yet implemented")


@router.post("/{execution_id}/retry")
def retry_execution(execution_id: str) -> dict:
    raise HTTPException(status_code=501, detail="Execution retry is not yet implemented")
