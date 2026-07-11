from fastapi import FastAPI

from app.api.routes import (
    ai_workspace_routes,
    execution_routes,
    model_routes,
    review_routes,
    session_routes,
    sse_routes,
    tool_routes,
    workspace_routes,
)
from app.config.settings import get_settings

# TODO integration: this is a standalone app for developing AI Workspace in isolation.
# On integration, DO NOT run this as a second FastAPI app alongside the existing
# TestGenWorkTop backend — instead, import these same routers into the existing app's real
# main.py and include them there (mirroring the original 25-file plan's `app.include_router`
# snippet), so AI Workspace shares the existing app's middleware, auth, and DB session setup
# instead of duplicating them.

settings = get_settings()
app = FastAPI(title="AI Workspace", version="0.1.0")

for router in (
    ai_workspace_routes.router,
    workspace_routes.router,
    execution_routes.router,
    review_routes.router,
    session_routes.router,
    model_routes.router,
    tool_routes.router,
    sse_routes.router,
):
    app.include_router(router, prefix=settings.api_prefix)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
