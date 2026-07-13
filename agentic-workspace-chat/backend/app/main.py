from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .bedrock import Bedrock
from .config import settings
from .custom_runtime import CustomToolStore, ToolProposal
from .models import ActionRequest, ApplyRequest, ChatRequest, ProposalRequest, WorkspaceRequest
from .tools import ToolRunner
from .workspace import apply_change, diff_for, files, read_text, resolve_file, resolve_workspace, sha

config = settings()
app = FastAPI(title="Agentic Workspace Chat", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)
proposals: dict[str, tuple[str, ProposalRequest]] = {}
actions: dict[str, tuple[str, ToolProposal]] = {}


@app.get("/api/health")
def health():
    return {"status": "ok", "region": config.aws_region, "model": config.bedrock_model_id}


@app.post("/api/workspaces/validate")
def validate(request: WorkspaceRequest):
    root = resolve_workspace(request.path, config)
    return {"path": str(root), "name": root.name, "isGit": (root / ".git").exists()}


@app.post("/api/workspaces/files")
def list_files(request: WorkspaceRequest):
    root = resolve_workspace(request.path, config)
    return {"files": files(root, config.workspace_max_files)}


@app.post("/api/chat")
def chat(request: ChatRequest):
    root = resolve_workspace(request.path, config)
    context = [(name, read_text(root, name, config.workspace_max_file_bytes)) for name in request.files]
    result = Bedrock(config).run(root, request.message, context)
    proposal = None
    if result.changes:
        proposal_request = ProposalRequest(path=str(root), changes=result.changes)
        proposal_id = str(uuid4())
        proposals[proposal_id] = (str(root), proposal_request)
        proposal = {"id": proposal_id, "changes": [
            {"path": change.path, "operation": change.operation, "diff": diff_for(root, change)}
            for change in result.changes
        ]}
    for action in result.actions:
        actions[action.id] = (str(root), action)
    return {"message": result.message, "proposal": proposal, "events": result.events, "actions": [
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
        {"path": change.path, "operation": change.operation, "diff": diff_for(root, change)}
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
        {"path": change.path, "operation": change.operation, "diff": diff_for(root, change)}
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
            apply_change(root, change)
    return {"applied": [change.path for change in proposal.changes if change.path in accepted]}
