from __future__ import annotations

from fastapi import APIRouter

from worktop.test_agent.app.schemas.generation_request import GenerationRequest
from worktop.test_agent.app.schemas.generation_result import GenerationResult
from worktop.test_agent.app.services.generation_orchestrator import GenerationOrchestrator

router = APIRouter(prefix="/api/playwright", tags=["playwright-generation"])


@router.post("/generate", response_model=GenerationResult)
def generate_playwright_test(request: GenerationRequest) -> GenerationResult:
    return GenerationOrchestrator().generate(request)
