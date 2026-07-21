import logging
import json
from time import monotonic
from uuid import uuid4
import asyncio
from threading import Event, Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from .bedrock import Bedrock
from .config import model_display_name, settings
from .custom_runtime import CustomToolStore, ToolProposal
from .session_store import SessionStore
from .models import ActionRequest, ApplyRequest, ChatRequest, CommandRequest, ProposalRequest, WorkspaceRequest
from .observability import configure_logging, request_id_var, session_id_var
from .resilience import wait_for_agent
from .tools import ToolRunner, run_safe_command
from .workspace import apply_change, apply_hunks, diff_for, diff_hunks, files, read_text, resolve_file, resolve_workspace, sha
from .workflows import classify_request
from .repository_index import build_index

logger = logging.getLogger("agentic-workspace-chat")

config = settings()
configure_logging(config.log_level, config.backend_log_dir)
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
    request_token = request_id_var.set(request_id)
    started = monotonic()
    logger.info("HTTP start method=%s path=%s", request.method, request.url.path)
    if config.api_auth_token and request.method != "OPTIONS" and request.url.path.startswith("/api/") and request.url.path not in {"/api/health", "/api/config"}:
        supplied = request.headers.get("authorization", "")
        token = supplied[7:] if supplied.lower().startswith("bearer ") else request.headers.get("x-api-key", "")
        if token != config.api_auth_token:
            logger.warning("HTTP rejected status=401 reason=authentication")
            request_id_var.reset(request_token)
            return JSONResponse(status_code=401, content={"detail": "Authentication required", "requestId": request_id}, headers={"x-request-id": request_id})
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > config.max_request_bytes:
        logger.warning("HTTP rejected status=413 reason=request_size")
        request_id_var.reset(request_token)
        return JSONResponse(status_code=413, content={"detail": "Request body exceeds configured limit", "requestId": request_id}, headers={"x-request-id": request_id})
    request.state.request_id = request_id
    try:
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        logger.info("HTTP complete status=%s elapsed_ms=%s", response.status_code, round((monotonic() - started) * 1000))
        return response
    except Exception:
        logger.exception("HTTP failed elapsed_ms=%s", round((monotonic() - started) * 1000))
        raise
    finally:
        request_id_var.reset(request_token)
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


@app.get("/api/sessions/{session_id}/execution")
def session_execution(session_id: str):
    return sessions.execution(session_id)


@app.post("/api/sessions/{session_id}/compact")
def compact_session(session_id: str):
    result = sessions.compact(session_id)
    logger.info("Session compacted messages=%s remaining=%s", result["compacted"], result["remaining"])
    return result


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
        "limits": {"maxRequestBytes": config.max_request_bytes, "maxMessageChars": 50_000,
                   "requestTimeoutSeconds": config.request_timeout_seconds},
        "features": {"streaming": True, "toolCalling": True, "reviewedEdits": True, "customTools": True},
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
    started = monotonic()
    root = resolve_workspace(request.path, config)
    discovered = files(root, config.workspace_max_files)
    logger.info("Workspace indexed name=%s files=%s elapsed_ms=%s", root.name, len(discovered), round((monotonic() - started) * 1000))
    return {"files": discovered}


@app.post("/api/workspaces/index")
def refresh_index(request: WorkspaceRequest):
    root = resolve_workspace(request.path, config)
    started = monotonic()
    result = build_index(root, config.workspace_max_files, config.agent_state_dir / "indexes", force=True)
    logger.info("Repository index refreshed files=%s symbols=%s elapsed_ms=%s", result["files"], result["indexed"], round((monotonic() - started) * 1000))
    return {key: result[key] for key in ("files", "indexed", "changed", "reused", "deleted")}


@app.post("/api/chat")
async def chat(request: ChatRequest, http_request: Request):
    started = monotonic()
    session_id_var.set(request.session_id or "-")
    root = resolve_workspace(request.path, config)
    context = [(name, read_text(root, name, config.workspace_max_file_bytes)) for name in request.files]
    logger.info("Chat accepted workspace=%s context_files=%s detail=%s", root.name, len(context), request.detail)
    history: list[dict] = []
    prior_plan: list[dict] = []
    if request.session_id:
        history = sessions.messages(request.session_id)
        prior_plan = next((m.get("plan") or [] for m in reversed(history) if m.get("role") == "assistant" and m.get("plan")), [])
        sessions.append(request.session_id, {"role": "user", "content": request.message, "contextFiles": request.files})
    cancel_event = Event()
    task = asyncio.create_task(asyncio.to_thread(
        Bedrock(config).run, root, request.message, context, request.detail, cancel_event, history, prior_plan
    ))
    result = await wait_for_agent(task, cancel_event, http_request, config.request_timeout_seconds)
    if result is None:
        logger.warning("Chat disconnected elapsed_ms=%s", round((monotonic() - started) * 1000))
        return {"message": "Generation stopped.", "proposal": None,
                "events": [{"tool": "cancel", "status": "success"}],
                "actions": [], "plan": [], "relationships": []}
    if request.session_id:
        sessions.append(request.session_id, {"role": "assistant", "content": result.message, "plan": result.plan, "usage": result.usage})
    payload = result_payload(root, result)
    logger.info(
        "Chat complete elapsed_ms=%s model_rounds=%s changes=%s actions=%s",
        round((monotonic() - started) * 1000),
        sum(1 for event in result.events if event.get("tool") == "model_round"),
        len(result.changes), len(result.actions),
    )
    return payload


def result_payload(root, result):
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
    return {"message": result.message, "proposal": proposal, "events": result.events, "plan": result.plan, "relationships": result.relationships, "usage": result.usage, "actions": [
        {"id": action.id, "name": action.name, "description": action.description,
         "code": action.code, "persistent": action.persistent, "inputPaths": action.input_paths}
        for action in result.actions
    ]}


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, http_request: Request):
    """Stream structured NDJSON progress while the synchronous Bedrock worker runs."""
    root = resolve_workspace(request.path, config)
    context = [(name, read_text(root, name, config.workspace_max_file_bytes)) for name in request.files]
    history: list[dict] = []
    prior_plan: list[dict] = []
    if request.session_id:
        history = sessions.messages(request.session_id)
        prior_plan = next((m.get("plan") or [] for m in reversed(history) if m.get("role") == "assistant" and m.get("plan")), [])
        sessions.append(request.session_id, {"role": "user", "content": request.message, "contextFiles": request.files})
    workflow = classify_request(request.message)
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    cancel_event = Event()
    execution_state = {"status": "running", "workflow": workflow.name, "plan": workflow.plan, "activity": "starting"}
    execution_lock = Lock()
    if request.session_id:
        sessions.save_execution(request.session_id, execution_state)

    def progress(event: dict) -> None:
        if request.session_id and event.get("type") in {"classified", "plan", "tool", "activity", "usage", "context"}:
            with execution_lock:
                if event.get("plan") is not None:
                    execution_state["plan"] = event["plan"]
                if event.get("type") in {"tool", "activity"}:
                    execution_state["activity"] = event.get("tool") or event.get("activity")
                if event.get("usage") is not None:
                    execution_state["usage"] = event["usage"]
                sessions.save_execution(request.session_id, execution_state)
        loop.call_soon_threadsafe(queue.put_nowait, event)

    worker = asyncio.create_task(asyncio.to_thread(
        Bedrock(config).run, root, request.message, context, request.detail, cancel_event,
        history, prior_plan, progress, workflow,
    ))

    async def events():
        started = loop.time()
        yield json.dumps({
            "type": "started", "workflow": workflow.name, "plan": workflow.plan,
            "requiresCheckpoint": workflow.requires_checkpoint and "[plan approved]" not in request.message.lower(),
        }) + "\n"
        try:
            while not worker.done() or not queue.empty():
                if await http_request.is_disconnected():
                    cancel_event.set()
                    logger.warning("Streaming client disconnected; cancellation requested")
                    return
                if loop.time() - started >= config.request_timeout_seconds:
                    cancel_event.set()
                    yield json.dumps({"type": "error", "message": f"Agent exceeded the {config.request_timeout_seconds}s request deadline"}) + "\n"
                    return
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=10)
                    yield json.dumps(event) + "\n"
                except asyncio.TimeoutError:
                    yield json.dumps({"type": "heartbeat", "elapsedSeconds": round(loop.time() - started)}) + "\n"
            result = await worker
            if request.session_id:
                sessions.append(request.session_id, {"role": "assistant", "content": result.message, "plan": result.plan, "usage": result.usage})
                sessions.save_execution(request.session_id, {"status": "completed", "workflow": workflow.name, "plan": result.plan, "usage": result.usage})
            yield json.dumps({"type": "completed", "result": result_payload(root, result)}) + "\n"
        except HTTPException as error:
            if request.session_id:
                sessions.save_execution(request.session_id, {**execution_state, "status": "failed", "error": str(error.detail)})
            yield json.dumps({"type": "error", "message": str(error.detail), "status": error.status_code}) + "\n"
        except Exception:
            logger.exception("Streaming chat failed")
            if request.session_id:
                sessions.save_execution(request.session_id, {**execution_state, "status": "failed"})
            yield json.dumps({"type": "error", "message": "The agent could not complete this request"}) + "\n"
        finally:
            if not worker.done():
                cancel_event.set()

    return StreamingResponse(events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
