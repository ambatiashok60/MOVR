import logging
from uuid import uuid4
import asyncio
from threading import Event

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .bedrock import Bedrock
from .config import model_display_name, settings
from .custom_runtime import CustomToolStore, ToolProposal
from .session_store import SessionStore
from .models import ActionRequest, ApplyRequest, ChatRequest, CommandRequest, ProposalRequest, WorkspaceRequest
from .tools import ToolRunner, run_safe_command
from .workspace import apply_change, apply_hunks, diff_for, diff_hunks, files, read_text, resolve_file, resolve_workspace, sha

logger = logging.getLogger("agentic-workspace-chat")

config = settings()
# repr() on purpose: it exposes stray quotes/brackets/whitespace that would
# make every workspace validation fail with 403 while the .env "looks right".
logger.info(
    "workspace_allowed_roots (effective runtime value): %r",
    [str(root) for root in config.workspace_allowed_roots],
)
app = FastAPI(title="Agentic Workspace Chat", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_guard(request: Request, call_next):
    """Apply optional API auth and a cheap pre-parse request-size guard."""
    request_id = request.headers.get("x-request-id") or str(uuid4())
    if config.api_auth_token and request.method != "OPTIONS" and request.url.path.startswith("/api/") and request.url.path not in {"/api/health", "/api/config"}:
        supplied = request.headers.get("authorization", "")
        token = supplied[7:] if supplied.lower().startswith("bearer ") else request.headers.get("x-api-key", "")
        if token != config.api_auth_token:
            return JSONResponse(status_code=401, content={"detail": "Authentication required", "requestId": request_id}, headers={"x-request-id": request_id})
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > config.max_request_bytes:
        return JSONResponse(status_code=413, content={"detail": "Request body exceeds configured limit", "requestId": request_id}, headers={"x-request-id": request_id})
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response
proposals: dict[str, tuple[str, ProposalRequest]] = {}
actions: dict[str, tuple[str, ToolProposal]] = {}
sessions = SessionStore(config.agent_state_dir)


@app.post("/api/sessions")
def create_session(request: WorkspaceRequest):
    return sessions.create(request.path)


@app.get("/api/sessions")
def list_sessions():
    return {"sessions": sessions.list()}


@app.get("/api/sessions/{session_id}/messages")
def session_messages(session_id: str):
    return {"messages": sessions.messages(session_id)}


@app.get("/api/health")
def health():
    return {"status": "ok", "region": config.aws_region, "model": config.bedrock_model_id,
            "authConfigured": bool(config.api_auth_token), "workspaceRoots": len(config.workspace_allowed_roots)}


@app.get("/api/config")
def runtime_config():
    return {
        "provider": "AWS Bedrock",
        "model": {"id": config.bedrock_model_id, "displayName": model_display_name(config.bedrock_model_id)},
        "region": config.aws_region,
        "authRequired": bool(config.api_auth_token),
        "limits": {"maxRequestBytes": config.max_request_bytes, "maxMessageChars": 50_000},
        "features": {"streaming": False, "toolCalling": True, "reviewedEdits": True, "customTools": True},
    }


@app.post("/api/workspaces/validate")
def validate(request: WorkspaceRequest):
    root = resolve_workspace(request.path, config)
    return {"path": str(root), "name": root.name, "isGit": (root / ".git").exists()}


@app.post("/api/commands/run")
def run_command(request: CommandRequest):
    """Run an explicitly approved, allowlisted command without a shell."""
    root = resolve_workspace(request.path, config)
    return run_safe_command(root, request.command, request.timeout_seconds)


@app.post("/api/workspaces/files")
def list_files(request: WorkspaceRequest):
    root = resolve_workspace(request.path, config)
    return {"files": files(root, config.workspace_max_files)}


@app.post("/api/chat")
async def chat(request: ChatRequest, http_request: Request):
    root = resolve_workspace(request.path, config)
    context = [(name, read_text(root, name, config.workspace_max_file_bytes)) for name in request.files]
    if request.session_id:
        sessions.append(request.session_id, {"role": "user", "content": request.message, "contextFiles": request.files})
    cancel_event = Event()
    task = asyncio.create_task(asyncio.to_thread(Bedrock(config).run, root, request.message, context, request.detail, cancel_event))
    while not task.done():
        if await http_request.is_disconnected():
            cancel_event.set()
            await task
            return {"message": "Generation stopped.", "proposal": None, "events": [{"tool": "cancel", "status": "success"}], "actions": [], "relationships": []}
        await asyncio.sleep(0.1)
    result = await task
    if request.session_id:
        sessions.append(request.session_id, {"role": "assistant", "content": result.message, "plan": result.plan})
    proposal = None
    if result.changes:
        proposal_request = ProposalRequest(path=str(root), changes=result.changes)
        proposal_id = str(uuid4())
        proposals[proposal_id] = (str(root), proposal_request)
        proposal = {"id": proposal_id, "changes": [
            {"path": change.path, "operation": change.operation, "diff": diff_for(root, change), "hunks": diff_hunks(diff_for(root, change))}
            for change in result.changes
        ]}
    for action in result.actions:
        actions[action.id] = (str(root), action)
    return {"message": result.message, "proposal": proposal, "events": result.events, "plan": result.plan, "relationships": result.relationships, "actions": [
        {"id": action.id, "name": action.name, "description": action.description,
         "code": action.code, "persistent": action.persistent, "inputPaths": action.input_paths}
        for action in result.actions
    ]}


@app.post("/api/actions/approve")
def approve_action(request: ActionRequest):
    stored = actions.pop(request.action_id, None)
    if not stored:
        raise HTTPException(404, "Action proposal not found or already handled")
    root_raw, action = stored
    if action.persistent:
        CustomToolStore(config).install(action)
        return {"installed": action.name, "proposal": None}
    root = resolve_workspace(root_raw, config)
    runner = ToolRunner(root, config)
    runner.run_action(action)
    proposal_request = ProposalRequest(path=str(root), changes=runner.changes())
    proposal_id = str(uuid4())
    proposals[proposal_id] = (str(root), proposal_request)
    return {"installed": None, "proposal": {"id": proposal_id, "changes": [
        {"path": change.path, "operation": change.operation, "diff": diff_for(root, change), "hunks": diff_hunks(diff_for(root, change))}
        for change in proposal_request.changes
    ]}}


@app.post("/api/proposals")
def propose(request: ProposalRequest):
    root = resolve_workspace(request.path, config)
    for change in request.changes:
        path = resolve_file(root, change.path)
        before = path.read_text() if path.exists() else ""
        change.original_sha256 = sha(before)
    proposal_id = str(uuid4())
    proposals[proposal_id] = (str(root), request)
    return {"id": proposal_id, "changes": [
        {"path": change.path, "operation": change.operation, "diff": diff_for(root, change), "hunks": diff_hunks(diff_for(root, change))}
        for change in request.changes
    ]}


@app.post("/api/proposals/apply")
def apply(request: ApplyRequest):
    stored = proposals.pop(request.proposal_id, None)
    if not stored:
        raise HTTPException(404, "Proposal not found or already applied")
    root_raw, proposal = stored
    root = resolve_workspace(root_raw, config)
    accepted = set(request.accepted_paths)
    for change in proposal.changes:
        if change.path in accepted:
            hunks = request.accepted_hunks.get(change.path)
            if hunks is not None and change.operation == "update":
                current = resolve_file(root, change.path).read_text()
                change.content = apply_hunks(current, diff_for(root, change), set(hunks))
            apply_change(root, change)
    return {"applied": [change.path for change in proposal.changes if change.path in accepted]}
