from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.api_repo_profile_service import ApiRepoProfileService

router = APIRouter(
    prefix="/api/api-test-generation",
    tags=["api-test-generation-repo-profile"],
)


class RepoProfileRequest(BaseModel):
    repo_path: str
    overwrite: bool = False


@router.post("/checkRepoProfile")
def check_repo_profile(request: RepoProfileRequest) -> dict:
    return {
        "status": "success",
        "data": ApiRepoProfileService().check(request.repo_path),
    }


@router.post("/generateRepoProfile")
def generate_repo_profile(request: RepoProfileRequest) -> dict:
    return {
        "status": "success",
        "data": ApiRepoProfileService().generate(
            request.repo_path,
            overwrite=request.overwrite,
        ),
    }
