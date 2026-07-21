# Local Setup with Conda

This setup keeps Python 3.11, Node.js 20, backend dependencies, and frontend
dependencies isolated from the system runtimes. The existing AWS CLI and cached
SSO session remain usable because the backend reads the normal `~/.aws` files.

## Prerequisites

- Conda, Miniconda, or Miniforge
- AWS CLI v2 configured with an SSO profile
- Amazon Bedrock access for Claude Sonnet 4.5

Verify Conda and AWS CLI:

```bash
conda --version
aws --version
```

## Create the Environment

From the `agentic-workspace-chat` directory:

```bash
conda env create -f environment.yml
conda activate agentic-workspace-chat
```

Verify the isolated runtimes:

```bash
python --version
node --version
npm --version
```

Expected major versions:

```text
Python 3.11
Node.js 20
```

If the environment already exists after `environment.yml` changes:

```bash
conda env update -f environment.yml --prune
conda activate agentic-workspace-chat
```

## Configure AWS and the Workspace

Create the local configuration at the project root. Do not place `.env` inside
the `backend` directory:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```dotenv
AWS_AUTH_MODE=sso
AWS_PROFILE=your-sso-profile
AWS_REGION=us-east-1
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

Set `AWS_AUTH_MODE=keys` instead when using direct credentials, then provide
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optional `AWS_SESSION_TOKEN`.
Keep these backend-only and never commit them.

Verify an existing authenticated SSO session:

```bash
aws sts get-caller-identity --profile your-sso-profile
```

If it has expired:

```bash
aws sso login --profile your-sso-profile
```

Conda does not require a separate AWS login when the existing cached session is
still valid.

## Install Frontend Dependencies

Enable pnpm through the Node 20 Corepack installation:

```bash
corepack enable
corepack prepare pnpm@latest --activate
cd frontend
pnpm install
cd ..
```

If Corepack is unavailable in the selected Conda Node package, use:

```bash
npm install --global pnpm
```

## Run the Application

Keep the Conda environment active in both terminals.

Terminal 1 — FastAPI:

```bash
conda activate agentic-workspace-chat
cd agentic-workspace-chat/backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Verify:

- `http://localhost:8000/api/health`
- `http://localhost:8000/docs`

Terminal 2 — Angular:

```bash
conda activate agentic-workspace-chat
cd agentic-workspace-chat/frontend
pnpm start
```

Open `http://localhost:4200`.

Do not use `python -m http.server` for normal local development. It cannot proxy
Angular `/api` requests to FastAPI. The Angular development server uses
`frontend/proxy.conf.json` to forward them to port 8000.

## Run Tests

Backend:

```bash
conda activate agentic-workspace-chat
cd agentic-workspace-chat/backend
pytest -q
```

Frontend type and Angular template checks:

```bash
conda activate agentic-workspace-chat
cd agentic-workspace-chat/frontend
pnpm exec tsc -p tsconfig.json --noEmit
pnpm exec ngc -p tsconfig.json
```

Production frontend build:

```bash
pnpm build
```

## Smoke Test

1. Confirm `/api/health` reports the configured region and model.
2. Open `http://localhost:4200`.
3. Connect a folder underneath `WORKSPACE_ALLOWED_ROOTS`.
4. Select multiple files or leave the selection empty for tool-based discovery.
5. Ask the agent to explain a relationship before testing modifications.
6. Request a small change and confirm a diff appears in the review panel.
7. Reject it first and verify no source file changes.
8. Repeat, keep the proposed file, and confirm only the approved file changes.

## Remove the Environment

Deactivate and remove it when it is no longer needed:

```bash
conda deactivate
conda env remove --name agentic-workspace-chat
```

The `.env`, `.agent-state`, and frontend `node_modules` directories are not
removed automatically.

## Troubleshooting

### The UI calls `/api/ai-workspace/...`

That is a different application in this repository. Start Angular from:

```text
agentic-workspace-chat/frontend
```

### Workspace is rejected

Ensure its resolved path is underneath one of the comma-separated paths in
`WORKSPACE_ALLOWED_ROOTS`, then restart FastAPI after changing `.env`.

### Bedrock reports an authentication error

By default the backend launches this command in its own terminal and retries
with a fresh session automatically. To diagnose the AWS CLI manually, run:

```bash
aws sso login --profile your-sso-profile
```

Also confirm the selected region supports the configured model and the SSO role
has permission to invoke it.

### Port already in use

Find the existing process or use matching alternative ports. If the backend
port changes, update `frontend/proxy.conf.json`. If the frontend port changes,
update `FRONTEND_ORIGIN` in `.env`.
