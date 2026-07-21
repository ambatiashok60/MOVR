# Running RepoAgent

How to run the backend, the local preview, the Angular frontend, and the tests —
plus configuration and troubleshooting. For the shared backend↔frontend contract
see [integration-contract.md](integration-contract.md).

---

## 1. Prerequisites

| Component | Requirement |
|-----------|-------------|
| Backend | Python **3.11+** |
| Backend deps | `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `pytest` (see `backend/requirements.txt`) |
| Frontend | Node **18+** and npm (Angular 17) |
| Real LLM (optional) | `boto3` + an AWS profile with Bedrock access |
| Preview | Nothing extra — served by the backend |

> The backend runs with a deterministic **FakeLLM** by default, so you need **no
> AWS setup** to run, demo, or test the whole system.

---

## 2. Recommended Conda setup

Create one environment for Python, Node.js, backend dependencies, and `boto3`:

```bash
cd repo-agent
conda env create -f environment.yml
conda activate repo-agent
```

To synchronize an existing environment after dependency changes:

```bash
conda env update -f environment.yml --prune
conda activate repo-agent
```

Complete the one-time local setup:

```bash
cd repo-agent
cp backend/.env.example backend/.env
# Edit backend/.env for your AWS profile and region.

cd frontend
npm install
cd ..
```

AWS CLI v2 is a separate host prerequisite for SSO. Verify it with
`aws --version`; do not store AWS access keys in the Conda environment.

---

## 3. Run backend and Angular UI together

With the `repo-agent` Conda environment active:

```bash
cd repo-agent
./run-dev.sh
```

Open **http://localhost:4200**. The launcher starts the backend on port 8080 and
Angular on port 4200. Press `Ctrl+C` once to stop both.

To debug the processes independently, use two terminals:

```bash
# Terminal 1
conda activate repo-agent
cd repo-agent/backend
./run.sh
```

```bash
# Terminal 2
conda activate repo-agent
cd repo-agent/frontend
npm start
```

---

## 4. Run only the backend (+ local preview)

```bash
cd repo-agent/backend
python3 -m pip install -r requirements.txt
./run.sh                       # → http://127.0.0.1:8080
```

`run.sh` starts `uvicorn app.main:app --host 127.0.0.1 --port 8080`. Any extra
arguments pass through (e.g. `./run.sh --reload` for autoreload during
development). It uses the active `repo-agent` Conda environment. If it is not
active, the script launches through `conda run -n repo-agent`; it will not
silently use an unrelated system Python. Override the environment name only when
needed with `REPO_AGENT_CONDA_ENV=another-name`.

Then open **http://127.0.0.1:8080/preview/**:

1. Enter a **workspace path** (an absolute path to a local repo/folder).
2. Choose **Ask** (read-only) or **Agent** (can modify files + run tools).
3. Type a request and hit **Send**.

The plan, tool calls, streamed response, relevant files, progress counters, and
validation all update live over SSE.

### Health check

```bash
curl http://127.0.0.1:8080/api/health
# {"status":"ok","version":"0.1.0","llm_provider":"fake","default_workspace":"…"}
```

---

## 5. Run against real AWS Bedrock

Use an **IAM Identity Center (SSO) token-provider profile** (refreshable), not
static keys:

```bash
cd repo-agent/backend
cp .env.example .env
# Edit .env and replace your-sso-profile with the profile from ~/.aws/config.
aws sso login --profile your-sso-profile     # once, if the session is expired
./run.sh
```

The backend loads `backend/.env` automatically because `run.sh` starts from the
backend directory. Real `.env` files are ignored by Git; `.env.example` is the
checked-in template. Store the AWS **profile name** here, not access keys or a
secret access key.

`boto3` is imported lazily and only required when the provider is `bedrock`. If
the SSO session expires mid-run, the backend automatically resets the session,
retries, and (if needed) triggers `aws sso login`, surfacing
`aws_reauthentication_required` / `aws_reauthenticated` to the UI **without
failing the run**.

---

## 6. Run the Angular frontend

```bash
cd repo-agent/frontend
npm install
npm start        # ng serve on http://localhost:4200, proxies /api → :8080
```

`proxy.conf.json` forwards `/api` (REST + SSE) to the backend on `:8080`, so run
the backend first. Production build:

```bash
npm run build    # → dist/repo-agent (static assets for any CDN/host)
```

> The `preview/` app is the build-free equivalent of the Angular UI; use it when
> you don't want a Node toolchain.

---

## 7. Tests

**Backend (pytest):**

```bash
cd repo-agent/backend
python3 -m pytest -q
```

Covers PathGuard sandbox escapes, Ask/Agent tool permission enforcement, full
Ask + Agent runs end-to-end, SSE monotonic sequence + replay, idempotent run
creation, conversation compaction, `apply_patch` hash-guard, the stale-run
watchdog, and the credential-error classifier / code-fence integrity.

**End-to-end (Playwright):**

```bash
cd repo-agent/frontend
npm install
npx playwright install chromium
npm run e2e      # boots the backend + preview, runs the lifecycle scenarios
```

Set `PLAYWRIGHT_BASE_URL=http://localhost:4200` to run the same specs against
the Angular dev server instead of the preview.

---

## 8. Configuration

All settings are environment variables with the `REPO_AGENT_` prefix (see
`backend/app/config.py`). The important ones:

| Variable | Default | Purpose |
|----------|---------|---------|
| `REPO_AGENT_LLM_PROVIDER` | `fake` | `fake` or `bedrock` |
| `REPO_AGENT_DATABASE_PATH` | `./data/repo_agent.db` | Zero-setup embedded state file; parent folder is created automatically |
| `REPO_AGENT_AWS_PROFILE` | `` | AWS SSO profile for Bedrock |
| `REPO_AGENT_AWS_REGION` | `us-east-1` | AWS region |
| `REPO_AGENT_BEDROCK_MODEL_ID` | Claude 3.5 Sonnet | Bedrock model id |
| `REPO_AGENT_MAX_AGENT_ITERATIONS` | `20` | Plan-Act-Observe-Decide loop cap |
| `REPO_AGENT_COMPACTION_TRIGGER_TURNS` | `16` | Start compacting conversation |
| `REPO_AGENT_RECENT_TURNS_TO_KEEP` | `6` | Turns kept verbatim after compaction |
| `REPO_AGENT_HEARTBEAT_INTERVAL_SECONDS` | `15` | SSE heartbeat cadence |
| `REPO_AGENT_RUN_STALE_FAILURE_SECONDS` | `600` | Watchdog fails a silent run |
| `REPO_AGENT_DEFAULT_COMMAND_TIMEOUT_SECONDS` | `120` | Per-command timeout |
| `REPO_AGENT_CORS_ALLOW_ORIGINS` | `http://localhost:4200,…` | Comma-separated CORS origins |

---

## 9. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `Workspace does not exist` (400) | The `workspace_path` must be an absolute path that exists on the **backend** host. |
| SSE stops updating in a browser/proxy | A proxy is buffering. The backend sets `X-Accel-Buffering: no` and sends heartbeats every 15s; ensure your proxy/LB idle timeout **exceeds** the heartbeat and doesn't buffer `text/event-stream`. |
| `boto3 is not installed` | You set `LLM_PROVIDER=bedrock` without `boto3`. `pip install boto3` or use `fake`. |
| `aws sso login` opens repeatedly | Expected only when the Identity Center session (not just role creds) has expired; logins are serialized per profile. |
| Agent mode "modified" a file you didn't expect | FakeLLM agent mode writes a namespaced `REPO_AGENT_NOTES.md`. Use Ask mode for read-only, or a throwaway workspace. |
| Tests can't find `app` module | Run pytest from `repo-agent/backend` (so `app` is importable). |
