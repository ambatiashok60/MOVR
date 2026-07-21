"""FastAPI application entrypoint.

Serves the REST + SSE API and the self-contained static preview at /preview, so
`uvicorn app.main:app` alone runs the whole demo.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

from app import __version__
from app.agents.run_service import get_run_service
from app.api import agent_router, conversation_router, stream_router, workspace_router
from app.config import settings
from app.logging.setup import configure_logging

_PREVIEW_DIR = Path(__file__).resolve().parents[2] / "preview"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    service = get_run_service()
    watchdog = asyncio.create_task(service.run_watchdog_forever())
    try:
        yield
    finally:
        watchdog.cancel()


app = FastAPI(title="RepoAgent", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workspace_router)
app.include_router(conversation_router)
app.include_router(agent_router)
app.include_router(stream_router)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "llm_provider": settings.llm_provider,
        # A sensible default so the preview is usable immediately.
        "default_workspace": str(_PREVIEW_DIR.parent),
    }


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/preview/")


if _PREVIEW_DIR.exists():
    app.mount("/preview", StaticFiles(directory=str(_PREVIEW_DIR), html=True), name="preview")
