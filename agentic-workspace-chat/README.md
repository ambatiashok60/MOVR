# Agentic Workspace Chat

Detailed design and delivery tracking:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md)
- [`docs/CONDA_SETUP.md`](docs/CONDA_SETUP.md) — isolated local setup and tests

## Installation

### Prerequisites

- Python 3.11 or newer
- Node.js 20 LTS (Angular 18 does not support the Node 14 runtime)
- `pnpm` 9+ or npm
- AWS CLI v2 configured with an IAM Identity Center/SSO profile
- Bedrock model access and `bedrock:InvokeModel` permission for Claude Sonnet
  4.5 in the configured region

### Angular 18 dependency status

This project intentionally targets Angular 18 and pins its final published
runtime release (`18.2.14`) plus compatible CLI/build packages. Current registry
audits report Angular security advisories whose suggested `18.2.15` patch was
never published; resolving them requires a planned upgrade to a supported newer
Angular major. Until that migration, keep this local workspace application bound
to loopback or a trusted development network and do not expose it as a public
web service. Deprecated `critters`, `glob`, `tar`, and `uuid` notices come from
the Angular build toolchain rather than direct application dependencies.

Use the committed `pnpm-lock.yaml` and avoid mixing npm and pnpm lockfiles:

```bash
pnpm install --frozen-lockfile
pnpm audit --prod
```

### 1. Configure the backend

From this project directory, create `.env` at the project root. The backend
intentionally loads `agentic-workspace-chat/.env`, not `backend/.env`:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
AWS_PROFILE=your-existing-sso-profile
AWS_REGION=us-east-1
AWS_AUTH_MODE=sso
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_MAX_TOKENS=8192
WORKSPACE_ALLOWED_ROOTS=/Users/you/Documents,/Users/you/Projects
WORKSPACE_MAX_FILES=10000
WORKSPACE_MAX_FILE_BYTES=1048576
AGENT_MAX_STEPS=12
AGENT_MAX_RESPONSE_CONTINUATIONS=3
AGENT_STATE_DIR=.agent-state
CUSTOM_TOOL_TIMEOUT_SECONDS=5
FRONTEND_ORIGIN=http://localhost:4200
```

For SSO mode, set `AWS_PROFILE` and authenticate with the AWS CLI. For static
key mode, set `AWS_AUTH_MODE=keys`, then provide `AWS_ACCESS_KEY_ID` and
`AWS_SECRET_ACCESS_KEY` (plus `AWS_SESSION_TOKEN` when using temporary keys).
The frontend never receives these values. Prefer SSO or short-lived role
credentials for development; do not commit `.env` or use long-lived keys in a
shared environment.

Multiple allowed roots are comma-separated. Keep them as narrow as practical.
If the SSO session is already valid, no new login is needed. Verify it with:

```bash
aws sts get-caller-identity --profile your-existing-sso-profile
```

If it is expired:

```bash
aws sso login --profile your-existing-sso-profile
```

### 2. Start FastAPI

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8000
```

Verify `http://localhost:8000/api/health`.

### 3. Start Angular

In another terminal:

```bash
cd frontend
pnpm install
pnpm start
```

Open `http://localhost:4200`.

### 4. Use the application

1. Paste a local folder underneath `WORKSPACE_ALLOWED_ROOTS` and connect it.
2. Optionally select multiple files. With no selection, the agent can discover
   relevant files using its workspace tools.
3. Describe the migration or implementation task.
4. Watch the tool activity and review proposed files in the right panel.
5. Keep or reject files, then apply only the accepted changes.
6. If the agent proposes a one-run or reusable custom tool, inspect its code and
   scope before approving it.

### Custom tool security model

Generated tools are constrained Python transformations with exactly one entry
point:

```python
def transform(files, args):
    return {"relative/path.ts": "new text content"}
```

They receive only an in-memory map of explicitly scoped text files. Imports,
`open`, dynamic evaluation, shell access, network access, environment variables,
and dunder introspection are rejected. Execution occurs in a child process with
a timeout. Results become proposals and still require ordinary diff approval.
Persistent tools are installed under `.agent-state/tools/` only after explicit
review; they are never installed merely because the model requested them.

## Goal

Build a local-first web application with an Angular 18 frontend and a Python
3.11+ FastAPI backend. A user selects a local workspace, optionally pins files
as context, chats with an AWS Bedrock model, and uses an agent to inspect and
modify the workspace through a diff-review-apply workflow. The workspace may be
a Git repository, but Git is optional.

## Proposed Structure

```text
agentic-workspace-chat/
├── frontend/                 Angular 18 application
├── backend/                  Python 3.11+ FastAPI application
├── docs/                     API, security, and architecture notes
├── scripts/                  Local development helpers
└── README.md
```

## Delivery Plan

### 1. Scaffold and local development

- Create a standalone Angular 18 application with a two-panel workspace/chat
  layout.
- Create a Python 3.11+ FastAPI service with typed settings, health endpoint,
  structured logging, and pytest coverage.
- Configure frontend-to-backend development proxying and environment-based API
  configuration.

### 2. Local workspace selection

- Let the user enter or choose a directory exposed to the locally running
  backend.
- Resolve and validate the path on the backend, establish it as the immutable
  root for the session, and reject path traversal and symlink escapes.
- Scan files with configurable size/count limits and default exclusions such as
  `.git`, `node_modules`, virtual environments, build output, binaries, and
  secrets.
- Detect Git when present and enable Git-specific metadata and diff tools only
  then; retain file browsing, search, and editing for ordinary directories.

### 3. Chat experience

- Add a workspace tree, selected-file/context chips, chat history, streaming
  responses, stop/regenerate controls, and clear error states.
- Allow explicit file attachment plus automatic context selection based on the
  request, while showing the user which files were sent to the model.
- Persist session metadata in a local filesystem state directory; do not copy
  entire workspaces into state storage.

### 4. AWS Bedrock through the existing SSO profile

- Keep AWS access entirely in the backend using `boto3`/`botocore` and the
  standard AWS credential chain.
- Accept an AWS profile name and region through backend configuration, create a
  `boto3.Session(profile_name=..., region_name=...)`, and use the Bedrock
  Runtime Converse/ConverseStream APIs.
- Depend on the developer completing `aws sso login --profile <profile>`; never
  send SSO tokens or AWS credentials to Angular or store them in application
  state.
- Add a startup/diagnostic endpoint that reports profile, region, Bedrock
  reachability, and available configured models without exposing secrets.
- Put model IDs and inference parameters in a backend allowlist so the UI can
  select only approved models.

### 5. Agentic tool loop

- Implement a provider-neutral model adapter with Bedrock as the first provider.
- Provide bounded, auditable tools for listing files, reading files, searching
  text, reading metadata, and inspecting Git status/diff when Git exists.
- Include create, patch, rename, and delete operations in the MVP. Agent edits
  are first written to an isolated proposal area, never directly to the selected
  workspace.
- Calculate a unified diff between the original workspace and the proposal,
  including new, changed, renamed, and deleted files. Use the same review model
  for Git and non-Git workspaces.
- Show the proposed changes in Angular with file-level and hunk-level review,
  syntax-aware side-by-side/unified diff views, change summaries, and warnings
  for conflicts or sensitive files.
- Let the user accept or reject individual files or hunks, revise the request,
  accept all, or discard the run. Apply only the accepted snapshot after an
  explicit confirmation.
- Detect changes made outside the app between proposal and apply. Refuse stale
  patches instead of overwriting newer content, and offer regeneration/rebase of
  the proposal.
- Create pre-image backups and an atomic apply journal so the entire approved
  change set can be rolled back. When Git exists, also display the resulting Git
  diff; Git commits remain a separate explicit user action.
- Add command execution later as a separate opt-in capability with a command
  allowlist, timeouts, output limits, working-directory confinement, and user
  approval.
- Bound every run by maximum steps, token budget, tool-output size, cancellation,
  and an execution timeout.

### 6. Safety and trust boundaries

- Treat workspace contents and model-generated tool calls as untrusted input.
- Redact or exclude common credential files by default and warn before including
  sensitive-looking content.
- Enforce workspace-root confinement for every tool call, not only at initial
  selection.
- Record an audit trail of prompts, selected context, tool requests, approvals,
  results, and applied changes.
- Provide backups or pre-image snapshots for writes when Git is unavailable.

### 7. API shape

- `POST /api/workspaces/validate`
- `POST /api/workspaces/scan`
- `GET /api/workspaces/{id}/files`
- `GET /api/workspaces/{id}/files/content`
- `POST /api/sessions`
- `POST /api/sessions/{id}/messages`
- `GET /api/sessions/{id}/events` (SSE)
- `GET /api/runs/{id}/changes`
- `POST /api/runs/{id}/review`
- `POST /api/runs/{id}/apply`
- `POST /api/runs/{id}/rollback`
- `POST /api/runs/{id}/cancel`
- `GET /api/models`
- `GET /api/aws/diagnostics`

### 8. Verification and rollout

- Unit-test path confinement, exclusions, context budgeting, Bedrock request
  mapping, tool validation, diff generation, stale-file detection, approval
  gates, atomic apply/rollback, and non-Git behavior.
- Add integration tests with a temporary workspace and a mocked Bedrock client.
- Add Angular component/service tests for workspace selection, streaming, tool
  approvals, and failures.
- Validate read-only chat and reviewed file editing together as the MVP, then add
  optional command execution as a separately controlled capability.

## Recommended MVP Boundary

The first usable milestone includes workspace validation, bounded file scanning,
explicit file context, streaming Bedrock chat through an existing SSO profile,
read tools, proposed multi-file modifications, diff review, selective approval,
atomic apply, and rollback. Command execution follows as a separately controlled
milestone because it has a wider security boundary than file editing.

## Initial Configuration

```dotenv
AWS_PROFILE=your-sso-profile
AWS_REGION=your-bedrock-region
BEDROCK_MODEL_IDS=approved-model-id-1,approved-model-id-2
WORKSPACE_ALLOWED_ROOTS=/path/to/allowed/parent
WORKSPACE_MAX_FILES=10000
WORKSPACE_MAX_FILE_BYTES=1048576
AGENT_MAX_STEPS=12
AGENT_STATE_DIR=.agent-state
```

The backend should fail with a clear remediation message when the SSO session is
missing or expired, asking the developer to refresh it with the AWS CLI.

## Current Agent Loop

One user request can now produce multiple Bedrock Converse calls. Claude Sonnet
4.5 can list workspace files, search text, read bounded line ranges, and create
an isolated proposal using exact replacements, new text files, or deletions.
The Angular review panel displays the resulting file diffs and applies only the
files the user keeps. The model never writes directly to the connected folder.

Detailed mode is an agent continuation workflow, not just a larger token limit:
the model explores with tools, produces a response, and if Bedrock stops at the
output boundary the backend asks it to continue without repeating itself. The
number of continuation generations is bounded by
`AGENT_MAX_RESPONSE_CONTINUATIONS`.

Sessions are stored without SQL under `.agent-state/sessions/` as metadata and
JSONL messages. **New session** creates a fresh backend session, clears the
current proposal and context in the UI, and keeps the connected workspace ready
for the next task.

## How File Editing Works

The model never writes directly to the connected folder. The edit lifecycle is:

```text
Explore/read
→ Propose create, replace, line-range edit, or delete
→ Build an in-memory proposal and unified diff
→ Review proposed files
→ Keep/reject selected files
→ Recheck original file hashes
→ Atomically apply approved files
```

For large files, the agent uses bounded line-range reads and the
`replace_line_range` tool. It can edit focused sections without putting the
entire file into one model request. Files above the configured size limit are
not read automatically; increase `WORKSPACE_MAX_FILE_BYTES` deliberately or
split the migration into smaller reviewed ranges. The actual workspace is not
modified until approval, and stale-file detection prevents overwriting changes
made outside the application.

Conversation persistence, live streaming events, hunk-level review, undo,
dependency graphs, MCP connections, and validation/repair tools remain planned.

## Run Locally

Node 20 LTS is recommended because Angular 18 does not support the Node 14
runtime currently installed on this machine.

```bash
cp .env.example .env
# Edit .env with your AWS SSO profile, region, and allowed workspace roots.
aws sso login --profile your-sso-profile

cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload

# In another terminal, from agentic-workspace-chat/frontend:
npm install
npm start
```

Open `http://localhost:4200`. The Angular development proxy sends `/api`
requests to FastAPI at `http://localhost:8000`.
