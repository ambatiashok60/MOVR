"""Agent-run lifecycle endpoints (§23)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agents.run_service import get_run_service
from app.models.agent import AgentRunRequest, AgentRunView, CreateRunResponse
from app.workspace.workspace_manager import WorkspaceError

router = APIRouter(prefix="/api/agent-runs", tags=["agent-runs"])


def _events_url(run_id: str) -> str:
    return f"/api/agent-runs/{run_id}/events"


@router.post("", response_model=CreateRunResponse, status_code=202)
async def create_run(body: AgentRunRequest) -> CreateRunResponse:
    service = get_run_service()
    try:
        run, _created = await service.create_run(body)
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CreateRunResponse(
        run_id=run.run_id, conversation_id=run.conversation_id,
        status=run.status, events_url=_events_url(run.run_id),
    )


@router.get("/by-client-request/{client_request_id}", response_model=AgentRunView)
def get_by_client_request(client_request_id: str) -> AgentRunView:
    from app.persistence.database import get_database
    from app.persistence.repositories import RunRepository

    run = RunRepository(get_database()).get_by_client_request_id(client_request_id)
    if not run:
        raise HTTPException(status_code=404, detail="No run for that client_request_id")
    return run


@router.get("/{run_id}", response_model=AgentRunView)
def get_run(run_id: str) -> AgentRunView:
    run = get_run_service().get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/{run_id}/cancel", response_model=AgentRunView)
async def cancel_run(run_id: str) -> AgentRunView:
    run = await get_run_service().cancel(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/{run_id}/revert")
async def revert_run(run_id: str) -> dict:
    reverted = await get_run_service().revert(run_id)
    return {"run_id": run_id, "reverted": reverted}


@router.get("/{run_id}/plan")
def get_plan(run_id: str) -> dict:
    from app.persistence.database import get_database
    from app.persistence.repositories import RunArtifactRepository

    plan = RunArtifactRepository(get_database()).get_plan(run_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No plan for run")
    return plan.model_dump()


@router.get("/{run_id}/response-batches")
def get_response_batches(run_id: str) -> list[dict]:
    from app.persistence.database import get_database
    from app.persistence.repositories import RunArtifactRepository

    batches = RunArtifactRepository(get_database()).list_response_batches(run_id)
    return [b.model_dump() for b in batches]


@router.get("/{run_id}/changes")
def get_changes(run_id: str) -> list[dict]:
    from app.persistence.database import get_database
    from app.persistence.repositories import RunArtifactRepository

    changes = RunArtifactRepository(get_database()).list_file_changes(run_id)
    return [c.model_dump() for c in changes]


@router.get("/{run_id}/validation")
def get_validation(run_id: str) -> list[dict]:
    from app.persistence.database import get_database
    from app.persistence.repositories import RunArtifactRepository

    results = RunArtifactRepository(get_database()).list_validation(run_id)
    return [r.model_dump() for r in results]
