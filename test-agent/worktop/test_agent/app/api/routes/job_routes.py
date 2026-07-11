from __future__ import annotations

from fastapi import APIRouter

from worktop.test_agent.app.schemas.generation_job import GenerationJob

router = APIRouter(prefix="/api/playwright/jobs", tags=["generation-jobs"])


@router.get("/{job_id}", response_model=GenerationJob)
def get_generation_job(job_id: str) -> GenerationJob:
    return GenerationJob(job_id=job_id, status="unknown")
