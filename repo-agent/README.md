# RepoAgent

A self-contained AI repository workspace: a FastAPI agent that inspects and edits
a local repo in **Ask** or **Agent** mode over AWS Bedrock, with a single-page UI.
Everything streams live over SSE with run recovery, conversation compaction, and
dead-hang prevention.

> This project is **standalone** — it does not import from any other folder in
> the surrounding repository.

## Layout

```
repo-agent/
├── backend/     FastAPI service (REST + SSE), the agent loop, tools, persistence
├── frontend/    Angular 17 single-page UI (three-pane workspace)
├── preview/     Self-contained static preview of the same UI (no build step)
└── docs/        architecture, TDD, security, operations, deployment, contracts
```

## Quick start (backend + local preview)

```bash
cd backend
python3 -m pip install -r requirements.txt   # fastapi, uvicorn, pydantic, pytest
./run.sh                                      # http://127.0.0.1:8080
```

Open **http://127.0.0.1:8080/preview/**. Enter a workspace path, pick Ask or
Agent, and send a request — the plan, tool calls, streamed response, relevant
files, progress counters, and validation all populate live.

By default the service uses a deterministic **FakeLLM**, so it runs with **zero
AWS setup**. To use real Bedrock:

```bash
cd backend
cp .env.example .env
# Edit .env and set REPO_AGENT_AWS_PROFILE to your AWS profile name.
```

`boto3` is imported lazily and only required when the provider is `bedrock`.
Expired SSO sessions trigger an automatic reset → retry → `aws sso login` →
retry ladder, surfaced to the UI as `aws_reauthentication_required` /
`aws_reauthenticated` without failing the run.

## Tests

```bash
cd backend
python3 -m pytest -q
```

Covers PathGuard sandbox escapes, Ask/Agent tool permission enforcement, full
Ask + Agent runs end-to-end, SSE monotonic sequence + replay, idempotent run
creation, conversation compaction, `apply_patch` hash-guard, the stale-run
watchdog, and the credential-error classifier / code-fence integrity.

All behavior changes follow a red-green-refactor TDD workflow. Start with the
[test strategy](docs/TESTING.md), then use the
[engineering guide](docs/ENGINEERING.md) for quality gates and review standards.

## Frontend (Angular)

```bash
cd frontend
npm install
npm start        # ng serve, proxies /api to the backend
```

Requires Node 18+. The `preview/` app is the build-free equivalent used for
local verification. See `docs/integration-contract.md` for the shared contract
both frontends follow.

## Configuration

All tunables are environment-overridable with the `REPO_AGENT_` prefix and may
be placed in `backend/.env` — see `backend/.env.example` and
`backend/app/config.py` (iteration caps, compaction thresholds, batch limits,
timeouts, heartbeat/stale-run windows, AWS profile/region/model).

## Architecture boundary

> The LLM decides *what* it wants to do. The backend decides whether it is
> allowed, how it runs, how much output comes back, and whether the result is
> valid.

The `PathGuard` sandbox, the tool permission map, output truncation, command
allowlist, and per-run snapshot/revert enforce that boundary.

## Engineering documentation

The [documentation index](docs/README.md) links the complete engineering set:
architecture, TDD/test strategy, contribution standards, security threat model,
operations/SLOs/runbooks, deployment, integration contracts, and ADR governance.
