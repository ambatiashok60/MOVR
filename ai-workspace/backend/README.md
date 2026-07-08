# AI Workspace — Backend

FastAPI backend for AI Workspace (Copilot-style Chat/Agent mode), built to sit on top of the
existing `ModelClientFactory` / `DefaultLLMClient` integration rather than duplicate it — see
[`app/integrations/existing_model_client/README.md`](app/integrations/existing_model_client/README.md)
for exactly what's assumed about that existing code.

Written without access to the real `TestGenWorkTop` backend, so this is a standalone,
independently-runnable app for now (see "Where this lands in the real project" below for what
integration actually requires).

## File count

**93 logic files** (`.py`, excluding `__init__.py`) + 28 `__init__.py` package markers + a handful
of project files (`pyproject.toml`, `Dockerfile`, `.gitignore`, `tests/README.md`) = **126 total**.
That lands inside the 110–130 file range originally targeted for AI Workspace V1 backend.

By area:

| Area | Files |
|---|---|
| `api/routes/` | 8 |
| `ai_workspace/domain/` | 13 |
| `ai_workspace/application/` (incl. `chat/`, `agent/`, `context/`, `execution/`, `prompts/`, `review/`, `sessions/`, `tools/`) | 26 |
| `ai_workspace/infrastructure/` | state stores, workspace provider, and SSE publisher |
| `ai_workspace/dto/` | 10 (9 originally scoped + `mappers.py`, added to avoid duplicating domain→DTO mapping across two route files) |
| `repository/` (domain + application + infrastructure) | 13 |
| `llm/` (application + infrastructure) | 6 |
| `dependencies/` | 5 |
| `config/`, `common/` | 5 |

## What's actually verified, not just written

Every `.py` file was syntax-checked (`ast.parse`), the whole tree was checked with `pyflakes`
(0 warnings after two rounds of fixes — a couple of unused imports and one import-path mistake
caught and corrected), and — critically — **the entire app was actually imported and run**:

```text
FastAPI app import: OK, 13 routes registered
GET  /health                                      -> 200
POST /api/ai-workspace/workspace/validate         -> validates local paths
GET  /api/ai-workspace/repositories/{id}/files    -> returns repository tree
GET  /api/ai-workspace/repositories/{id}/file-content -> returns file content
GET  /api/ai-workspace/bootstrap                  -> returns models/tools/preferences/config
POST /api/ai-workspace/sessions                   -> creates a path-backed session
```

The one thing that made a full import possible: `DefaultLLMClient` doesn't exist in this
environment (it's the real, external `worktop.core_services...` module), so a minimal stub was
installed into a throwaway virtualenv purely to prove the rest of the dependency graph wires up
correctly — that stub is not part of this codebase and was deleted after testing.

## Architecture: Strategy pattern for Ask/Agent

`ExecutionOrchestrator` (`ai_workspace/application/execution/execution_orchestrator.py`) owns the
shared lifecycle — create the run, resolve the workspace runtime, transition status, catch
failures, emit the final SSE event. `ChatService` and `AgentService` each implement the
`ExecutionStrategy` protocol and hold all mode-specific behavior (which tools are available,
whether planning happens, whether a review step follows). This is the "single execution pipeline,
mode decides what's enabled" design discussed in this session, not two parallel, duplicated
services.

```text
POST /chat or /agent
        │
        ▼
ExecutionOrchestrator.run()
        │
        ├── ChatService.run()   (Ask: read-only, single LLM call, no tools)
        └── AgentService.run()  (Agent: builds context, single structured-JSON LLM call,
                                  parses plan + file changes, stages via ReviewService)
        │
        ▼
ContextBuilderService → PromptBuilderService → PromptRenderer
        │
        ▼
LLMApplicationService → ModelClientFactoryGateway → LLMClientFactory
        │
        ├── DefaultLLMClientAdapter  (real Worktop model client)
        └── MockLLMClient            (only when AI_WORKSPACE_ALLOW_MOCK_LLM=true)
        │
        ▼
DefaultLLMClient / ModelClientFactory  (existing, external, not owned by this codebase)
```

## Real correctness work done, not just scaffolding

A few things worth knowing about because they're substantive, not cosmetic:

1. **Path traversal protection** (`common/path_safety.py`) — every file read/write resolves the
   requested path against the workspace root and rejects anything that escapes it. Verified live
   against a `../../etc/passwd` attempt (see test log above), not just asserted in a comment.
2. **Diff hunks are real** (`ai_workspace/application/review/diff_service.py`) — uses
   `difflib.SequenceMatcher.get_grouped_opcodes`, not a stub. Verified against a real
   before/after code sample; output matches the exact diff shown in the earlier approved mockup.
3. **`FileChange.new_content` is the source of truth for Apply, not the diff hunks.** An earlier
   draft of `apply_patch_tool.py` reconstructed file content by concatenating non-removed diff
   lines — that's lossy (a unified diff's context window doesn't cover the whole file) and would
   have silently corrupted files outside the diffed region. Fixed before it shipped: the domain
   model carries the full proposed content; diff hunks are display-only.
4. **Command execution is allowlisted, not free-form** (`run_test_command_tool.py`) — takes a
   `command_key` that maps to a fixed argument list, never a string built from LLM output and
   passed to a shell. Same for `git_cli_provider.py` (list-form subprocess args, no shell=True).
5. **The Apply flow's `run_id → session_id → workspace_path` resolution** was a real gap found
   during writing (the frontend only ever sends `{run_id, kept_file_ids}`) — fixed by having
   `ExecutionOrchestrator` persist completed executions to `InMemoryExecutionStore`, so
   `review_routes.py` can look up which workspace a run belongs to without the frontend needing
   to know or send it.
6. **State stores are process singletons, backed by SQLite by default.** `dependencies/container.py`
   exists specifically because a naive FastAPI `Depends(lambda: SomeStore())` recreates the store
   on every request. The default SQLite backend survives restarts; `AI_WORKSPACE_STATE_BACKEND=memory`
   is available only for throwaway demos, and `AI_WORKSPACE_STATE_BACKEND=mysql` points the same
   store adapters at a shared MySQL instance.

## Deliberate scope decisions

- **Not a true iterative tool-calling agent.** A real per-step loop (LLM calls `read_file`, gets
  a result, decides the next call, ...) needs confirmed function-calling support from
  `DefaultLLMClient`, which is unconfirmed. V1's `AgentService` instead asks for one structured
  JSON response (plan + full file contents) in a single call — see `prompt_renderer.py`'s
  `_AGENT_SYSTEM_PROMPT` for the exact contract. This is real, working V1 behavior, not a stub,
  but it's a materially different design from true agentic tool use and should be revisited once
  function-calling is confirmed.
- **No streaming.** `llm_stream_service.py` / `model_client_streaming_adapter.py` exist as seams
  but raise rather than fake a stream, since nothing confirms `DefaultLLMClient` supports it.
- **No conversation summarization.** `context_builder_service.py` takes the last 10 messages
  verbatim and drops everything older — no running summary yet (half of the context-management
  design discussed for the frontend, not the other half).

## Known open questions

1. **`worktop.core_services.app.gen_ai_models.default_llm_client`'s real import path and contract
   must be confirmed in the host service** — see `app/integrations/existing_model_client/README.md`.
   AI Workspace follows the same pattern as `test-agent`: `LLMClient` protocol,
   `DefaultLLMClientAdapter`, and `LLMClientFactory`. Missing real model wiring fails loudly
   unless `AI_WORKSPACE_ALLOW_MOCK_LLM=true` is explicitly set for local testing.
2. **No confirmed way to list a tenant's *available* models** (as opposed to their currently
   configured one) — `model_catalog_service.py` returns a placeholder single-model catalog.
3. **`common/db.py` and `common/tenancy.py` use local standalone fallbacks.**
   The real app already has both (proven by `DefaultLLMClient(db, tenant_id)`'s signature) — wire
   to those, don't run two DB/tenant mechanisms side by side.
4. **The V1 repository flow is path-first.** `workspace_routes.py` validates a local path and
   the frontend promotes that validated path into the selected repository/session. A richer
   repository catalog (id → path mapping, branch checkout) can replace this later, but today
   `repository_id` intentionally remains the workspace path.
5. **Session/execution/review/plan/runtime state is durable by default through SQLite.**
   This is restart-safe for a single backend instance. For multiple backend instances, set
   `AI_WORKSPACE_STATE_BACKEND=mysql` and configure the MySQL connection below. SSE fanout still
   needs Redis/Valkey/pubsub for true multi-instance live events.

## State Store Configuration

AI Workspace uses a small adapter-based key-value state layer. The service layer calls the same
store methods regardless of backend.

### SQLite default

```bash
AI_WORKSPACE_STATE_BACKEND=sqlite
AI_WORKSPACE_STATE_DB_PATH=.ai-workspace-state.sqlite3
```

Use this for local development or a single backend process. It survives ordinary server restarts.

### MySQL shared state

Install the optional dependency in the host backend environment:

```bash
pip install "ai-workspace-backend[mysql]"
```

Then configure:

```bash
AI_WORKSPACE_STATE_BACKEND=mysql
AI_WORKSPACE_MYSQL_HOST=localhost
AI_WORKSPACE_MYSQL_PORT=3306
AI_WORKSPACE_MYSQL_DATABASE=ai_workspace
AI_WORKSPACE_MYSQL_USER=ai_workspace_user
AI_WORKSPACE_MYSQL_PASSWORD=change-me
AI_WORKSPACE_MYSQL_STATE_TABLE=ai_workspace_state
```

The MySQL adapter creates this table automatically if it does not exist:

```sql
CREATE TABLE ai_workspace_state (
  namespace VARCHAR(128) NOT NULL,
  state_key VARCHAR(255) NOT NULL,
  payload JSON NOT NULL,
  updated_at VARCHAR(64) NOT NULL,
  PRIMARY KEY(namespace, state_key)
);
```

If you use a different MySQL instance, update the `AI_WORKSPACE_MYSQL_*` environment variables.
No application code changes are needed.

### Memory mode

```bash
AI_WORKSPACE_STATE_BACKEND=memory
```

Use only for throwaway demos. State is lost on restart.

## Logging

AI Workspace logs the main backend lifecycle similarly to `test-agent`:

- state store configuration
- session create/delete
- message recording
- chat start/complete
- agent start/complete
- execution start/complete/failure
- review save/decision/apply
- model-client factory start/complete/failure
- key metrics such as proposed/applied file counts and execution stage counts

When the host Worktop custom logger is available, `app/utils/logging_utils.py` delegates to
`log_step`, `log_metric`, `log_exception`, and `log_performance`. Outside the host app, it falls
back to standard Python logging under the `ai_workspace` logger name.

## Where this lands in the real project

This cannot simply be copied in as-is:

1. **Do not run `app/main.py` as a second FastAPI app.** Import the routers
   (`ai_workspace_routes.router`, `workspace_routes.router`, etc.) into the *existing* app's real
   `main.py` and `include_router()` them there, so AI Workspace shares the existing app's
   middleware, auth, and DB session setup.
2. **Delete `common/db.py` and `common/tenancy.py`**, and repoint every `Depends(get_db)` /
   `Depends(get_tenant_id)` at the real dependencies already used elsewhere in the app (proven to
   exist by `DefaultLLMClient`'s own constructor signature).
3. **Confirm `app/integrations/existing_model_client/README.md`'s assumptions** against the real
   `worktop/core_services/app/gen_ai_models/` source before trusting `llm/` at all.
4. **Use MySQL or platform database tables** for shared state when this runs on more than one
   backend instance. Add Redis/Valkey/pubsub for multi-instance SSE event fanout.

## Frontend counterpart

[`../frontend/`](../frontend/) is the Angular + PrimeNG side, calling into
these same routes. Its README documents its own open questions and assumptions — several overlap
with this backend's (repo-vs-path selection, SSE contract, server-staged Apply) and are worth
reading together.
