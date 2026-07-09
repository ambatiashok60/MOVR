from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api_test_generation_request import (
    GenerateApiTestCodeRequest,
    GenerateApiTestsRequest,
)
from app.schemas.queued_task import QueuedTask
from app.task_managers.api_test_generation_task_manager import (
    enqueue_api_tests_task,
    enqueue_api_test_code_generation_task,
)

router = APIRouter(
    prefix="/api/api-test-generation",
    tags=["api-test-generation"],
)


@router.post("/generate-api-test-code", response_model=QueuedTask)
def generate_api_test_code(request: GenerateApiTestCodeRequest) -> QueuedTask:
    task_id = enqueue_api_test_code_generation_task(request)
    return QueuedTask(task_id=task_id)


@router.post("/generateApiTests", response_model=QueuedTask)
def generate_api_tests(request: GenerateApiTestsRequest) -> QueuedTask:
    task_id = enqueue_api_tests_task(request)
    return QueuedTask(task_id=task_id)
