from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api_scenario_request import GenerateApiScenariosRequest
from app.schemas.queued_task import QueuedTask
from app.task_managers.api_test_generation_task_manager import (
    enqueue_api_scenario_generation_task,
)

router = APIRouter(
    prefix="/api/api-test-generation",
    tags=["api-test-generation"],
)


@router.post("/generate-api-scenarios", response_model=QueuedTask)
def generate_api_scenarios(request: GenerateApiScenariosRequest) -> QueuedTask:
    task_id = enqueue_api_scenario_generation_task(request)
    return QueuedTask(task_id=task_id)
