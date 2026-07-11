from __future__ import annotations


from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from worktop.test_agent.app.api.routes.event_routes import router as event_router
from worktop.test_agent.app.api.routes.generation_routes import router as generation_router
from worktop.test_agent.app.api.routes.job_routes import router as job_router
from worktop.test_agent.app.config import settings
from worktop.test_agent.app.errors import UnsupportedRepositoryError
from worktop.test_agent.app.logging_config import configure_logging
from worktop.test_agent.utils.logging import get_logger

configure_logging()
logger = get_logger(__name__)

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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "[playwright-generation] stage=api_request status=failed path=%s error=%s",
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "playwright_generation_failed",
            "message": str(exc),
        },
    )
