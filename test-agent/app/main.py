from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.event_routes import router as event_router
from app.api.routes.generation_routes import router as generation_router
from app.api.routes.job_routes import router as job_router
from app.config import settings
from app.errors import UnsupportedRepositoryError


app = FastAPI(title=settings.app_name)
app.include_router(generation_router)
app.include_router(job_router)
app.include_router(event_router)


@app.exception_handler(UnsupportedRepositoryError)
async def unsupported_repository_handler(
    request: Request,
    exc: UnsupportedRepositoryError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "unsupported_repository",
            "message": str(exc),
            "repo_profile": exc.profile.model_dump(),
        },
    )
