from fastapi import APIRouter, Depends, HTTPException

from app.ai_workspace.application.sessions.session_service import SessionService
from app.ai_workspace.application.workspace_runtime_service import WorkspaceRuntimeService
from app.ai_workspace.domain.chat_message import ChatRole
from app.ai_workspace.domain.workspace_mode import WorkspaceMode
from app.ai_workspace.dto.chat_dto import ChatRequest
from app.ai_workspace.dto.chat_dto import ChatMessageDto
from app.ai_workspace.dto.session_dto import CreateSessionRequest, SessionDto
from app.common.tenancy import get_tenant_id
from app.dependencies.ai_workspace_dependencies import get_session_service, get_workspace_runtime_service

router = APIRouter(prefix="/ai-workspace/sessions", tags=["Sessions"])


@router.post("", response_model=SessionDto)
def create_session(
    request: CreateSessionRequest,
    tenant_id: str = Depends(get_tenant_id),
    session_service: SessionService = Depends(get_session_service),
    runtime_service: WorkspaceRuntimeService = Depends(get_workspace_runtime_service),
) -> SessionDto:
    session = session_service.create_session(tenant_id, request.repository_id, request.branch, WorkspaceMode.AGENT)
    # repository_id here is used as the workspace_path — see workspace_routes.py's open question
    # about reconciling the repo-id-based flow with the raw-path validation flow (same gap
    # flagged on the frontend side, in ai-workspace/frontend/README.md).
    runtime_service.start(session.id, workspace_path=request.repository_id, mode=WorkspaceMode.AGENT)
    return _to_dto(session)


@router.get("", response_model=list[SessionDto])
def list_sessions(
    repository_id: str | None = None, session_service: SessionService = Depends(get_session_service)
) -> list[SessionDto]:
    return [_to_dto(s) for s in session_service.list_sessions(repository_id)]


@router.get("/{session_id}", response_model=SessionDto)
def get_session(session_id: str, session_service: SessionService = Depends(get_session_service)) -> SessionDto:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _to_dto(session)


@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
    runtime_service: WorkspaceRuntimeService = Depends(get_workspace_runtime_service),
) -> dict:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session_service.delete_session(session_id)
    runtime_service.stop(session_id)
    return {"ok": True}


@router.get("/{session_id}/messages", response_model=list[ChatMessageDto])
def get_messages(session_id: str, session_service: SessionService = Depends(get_session_service)) -> list[ChatMessageDto]:
    messages = session_service.get_messages(session_id)
    return [
        ChatMessageDto(
            id=m.id, session_id=m.session_id, role=m.role.value, content=m.content, created_at=m.created_at,
            execution_id=m.execution_id,
        )
        for m in messages
    ]


@router.post("/{session_id}/messages", response_model=ChatMessageDto)
def add_message(
    session_id: str,
    request: ChatRequest,
    session_service: SessionService = Depends(get_session_service),
) -> ChatMessageDto:
    message = session_service.record_message(session_id, ChatRole.USER, request.prompt)
    return ChatMessageDto(
        id=message.id,
        session_id=message.session_id,
        role=message.role.value,
        content=message.content,
        created_at=message.created_at,
        execution_id=message.execution_id,
    )


@router.get("/{session_id}/context")
def get_context_summary(
    session_id: str,
    runtime_service: WorkspaceRuntimeService = Depends(get_workspace_runtime_service),
) -> dict:
    runtime = runtime_service.get(session_id)
    selected_paths = runtime.selected_file_paths if runtime else []
    return {
        "sessionId": session_id,
        "fileCount": len(selected_paths),
        "tokenCount": 0,
        "files": [{"path": path, "isPriority": True} for path in selected_paths],
        "tokenUsage": {
            "inputTokens": 0,
            "reservedOutputTokens": 0,
            "budgetTokens": 0,
        },
    }


@router.put("/{session_id}/context")
def set_context_summary(
    session_id: str,
    payload: dict,
    runtime_service: WorkspaceRuntimeService = Depends(get_workspace_runtime_service),
) -> dict:
    runtime_service.set_selected_files(session_id, payload.get("filePaths", []))
    return get_context_summary(session_id, runtime_service)


def _to_dto(session) -> SessionDto:
    return SessionDto(
        id=session.id,
        repository_id=session.repository_path,
        branch=session.branch,
        mode=session.mode.value,
        current_task=session.current_task,
        started_at=session.started_at,
        last_activity_at=session.last_activity_at,
    )
