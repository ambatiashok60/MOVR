from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from worktop.api_agent.app.api.routes.api_scenario_routes import router as scenario_router
from worktop.api_agent.app.api.routes.api_test_generation_routes import router as generation_router
from worktop.api_agent.app.api.routes.event_routes import router as event_router
from worktop.api_agent.app.api.routes.job_routes import router as job_router
from worktop.api_agent.app.api.routes.repo_profile_routes import router as repo_profile_router
from worktop.api_agent.app.config import settings
from worktop.api_agent.app.errors import ApiAgentError, TaskNotFoundError


app = FastAPI(title=settings.app_name)
app.include_router(scenario_router)
app.include_router(generation_router)
app.include_router(job_router)
app.include_router(event_router)
app.include_router(repo_profile_router)


@app.exception_handler(TaskNotFoundError)
async def task_not_found_handler(
    request: Request,
    exc: TaskNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "task_not_found", "message": str(exc), "task_id": exc.task_id},
    )


@app.exception_handler(ApiAgentError)
async def api_agent_error_handler(
    request: Request,
    exc: ApiAgentError,
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": "api_agent_error", "message": str(exc)})
