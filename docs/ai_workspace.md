# AI Workspace — Design Doc (V1)

## Relationship to Worktop

[roadmap.md](roadmap.md), [analysis.md](analysis.md), [current_repo.md](current_repo.md), and [structure.md](structure.md)
describe **Worktop**: a repository-aware platform that discovers a codebase's testing
ecosystem and generates CI/Stage API integration tests through an 8-agent intelligence +
generation pipeline (Project Intelligence → Change Intelligence → ... → Validation & Reporting).

**AI Workspace is a separate, more general module.** It is not another Worktop capability
(Story Intelligence, Coverage Intelligence, etc.) — it's a Copilot Chat / Copilot Agent style
surface embedded in the same platform, built on the existing `ModelClientFactory` and backend
conventions. Worktop's specialized agents may later be exposed *through* AI Workspace as tools,
but AI Workspace itself must not absorb their logic.

The concrete stack has been confirmed:

- **Frontend**: Angular, at `TestGenWorkTop_UI/`
- **Backend**: FastAPI, at `worktop/`
- **Existing LLM adapter to reuse (do not replace)**: `worktop/core_services/app/gen_ai_models/model_client_factory.py`

The full existing codebase is on another system, not available in this working directory. Actual
edits to existing files (`app-constants.ts`, `app.routes.ts`, `main.py`) require their current
contents to be pasted in before a precise diff can be produced — until then, snippets below are
best-effort based on the described conventions.

---

## What we are building

AI Workspace — similar to Copilot Chat + Copilot Agent, but inside the platform.

It lets a developer select a local workspace path, chat with the repository, ask questions,
run an agent, review file changes, and apply/reject them.

---

## Product flow

```text
Developer opens AI Workspace
        ↓
Selects local repo path
        ↓
Backend validates path and scans repo context
        ↓
Create or resume session
        ↓
User chooses Chat Mode or Agent Mode
        ↓
Model/tool metadata comes from backend
        ↓
AI uses selected repo context + priority files
        ↓
Ask / Agent messages saved to session
        ↓
Chat Mode answers only
Agent Mode plans + reads/writes files through tools
        ↓
Agent run linked to session; file changes linked to session/run
        ↓
Frontend shows live SSE timeline
        ↓
User reviews changed files
        ↓
User keeps / rejects / applies changes
        ↓
User can revisit history later
```

---

## Scope — in for V1

```text
AI Workspace
├── Chat Mode / Ask Mode
├── Agent Mode
├── Local workspace path validation
├── Repository scan for context
├── Priority file selection
├── Model registry from backend
├── Tool registry from backend
├── Prompt/context builder
├── LLM integration using existing ModelClientFactory
├── File read/write tools
├── Git diff tool
├── Test command tool
├── Execution planning
├── SSE timeline
├── Review changed files
├── Keep/reject/apply changes
└── Session history
```

## Scope — explicitly out for V1

```text
Not part of AI Workspace V1
├── Story Intelligence
├── Jira analysis
├── Ambiguity scoring
├── Coverage Intelligence
├── Suite Optimizer
├── Code Health Intelligence
├── Stage regression intelligence
└── Existing test intelligence as a separate module
```

These map to Worktop's own logical capabilities (see [roadmap.md](roadmap.md)) and belong as
separate left-nav modules later. They may *reuse* AI Workspace services (chat surface, SSE
timeline, review panel) but must not be built inside AI Workspace, and AI Workspace must not
be built to anticipate them.

---

## Concrete V1 integration plan — frozen at 33 files

This supersedes the earlier abstract ~110–130 backend / ~78 frontend estimates, which assumed a
tech-agnostic layout (`app/repository/`, `app/llm/`, etc.). Those broader boundaries — a
stack-agnostic repository layer, an LLM gateway abstraction, generalized tool/session
infrastructure — are still the right *direction* for AI Workspace to grow into as more modules
reuse it, but V1 is scoped tightly to shipping the tab: Ask mode, Agent mode, Keep/Reject,
selective apply, session/history persistence, and a first-class context-management layer, wired
directly into the existing Angular + FastAPI conventions.

Scope evolution: 25 (base Ask/Agent/review) → 29 (added session + conversation history, so a user
can resume a prior task) → **33, frozen for V1 beta** (promoted context assembly, token budgeting,
and prompt construction from implicit logic buried in the orchestrator into three first-class
services, plus split file-level tool access out of repository-level tool access). This is the
scope freeze — the goal is the right foundation, not maximal features. Explicitly deferred past
this line: background workers, distributed queues, MCP servers, advanced retrieval infrastructure,
and `response_chunk_service.py` for long-response chunking — none of these are earned yet at V1's
usage scale and can be layered on later without changing this design.

### Frontend — Angular (`TestGenWorkTop_UI/`)

New:

```text
src/app/pages/ai-workspace/
├── ai-workspace.component.ts
├── ai-workspace.component.html
├── ai-workspace.component.scss
├── models/
│   ├── ai-repository.model.ts
│   ├── ai-chat.model.ts
│   ├── ai-agent-run.model.ts
│   └── ai-file-change.model.ts
└── services/
    └── ai-workspace.service.ts
```

Updated:

```text
src/app/app.routes.ts           — lazy route for /ai-workspace
src/app/config/app-constants.ts — new left-nav entry (AI Workspace, pi-sparkles)
```

Session support does **not** add new frontend files for V1 — it updates 5 existing ones instead:
`ai-workspace.component.ts`, `ai-workspace.component.html`, `ai-workspace.service.ts`,
`ai-chat.model.ts`, `ai-agent-run.model.ts`. A dedicated History component is deferred unless the
inline session list in the main component proves insufficient.

`ai-workspace.service.ts` calls: `getRepositories()`, `getBranches(repoId)`,
`getFiles(repoId, branch)`, `ask(payload)`, `runAgent(payload)`, `applyChanges(payload)`,
`createSession()`, `listSessions()`, `getSession(sessionId)`, `sendMessage(sessionId, payload)`,
`getMessages(sessionId)`.

UI layout (per approved mockup — Angular + PrimeNG):

```text
AI Workspace Page
├── Header — Repository dropdown (p-select), Branch dropdown (p-select), sync status, Refresh
├── Mode Selector — Ask / Agent (p-tabs / p-selectbutton)
├── Left Panel
│   ├── Repository Explorer / History (p-tabs + p-tree for file tree)
│   └── Context — file count + token count, Manage action (surfaces context_budget_manager.py)
├── Center Panel
│   ├── Quick-action shortcuts (p-button, outlined) — e.g. Explain this code, Refactor module,
│   │   Add logging, Generate tests — pre-fill the task input, not separate endpoints
│   ├── Task input + Run button
│   ├── Chat thread (user + AI Workspace turns, p-card)
│   ├── "N files changed" summary with per-file +/- line counts and inline Keep/Reject
│   └── Follow-up input, separate from the initial task input
└── Right Panel — "Changes" header (kept/rejected counts, Review Summary action), per-file diff
    list (status badge: Modified, kept ✓ / rejected ✗), hunk-level diff viewer (custom renderer,
    no PrimeNG diff component), footer showing "N files selected" + Apply Changes (split button)
```

This mockup resolves open question #4: Keep/Reject is staged client-side (or server-staged per
run, TBD) before Apply — the footer's "Only kept files will be applied to the repository" copy
confirms `apply_changes_service.py` writes only the kept subset on an explicit Apply action, not
immediately on Keep.

### Backend — FastAPI (`worktop/`)

New module:

```text
worktop/ai_workspace/
├── api/
│   └── ai_workspace_controller.py
├── models/
│   ├── ai_workspace_models.py
│   └── ai_session_models.py
├── service/
│   ├── ai_workspace_service.py
│   ├── ai_agent_orchestrator.py
│   ├── repository_context_service.py
│   ├── context_builder_service.py      ← new, first-class
│   ├── context_budget_manager.py       ← new, first-class
│   ├── prompt_builder_service.py       ← new, first-class
│   ├── conversation_history_service.py
│   ├── agent_session_service.py
│   ├── change_planner_service.py
│   ├── diff_service.py
│   └── apply_changes_service.py
├── repository/
│   └── ai_workspace_repository.py
├── tools/
│   ├── repository_reader_tool.py
│   ├── repository_search_tool.py       ← renamed from file_search_tool.py
│   ├── file_reader_tool.py             ← new — split out of repository_reader_tool.py
│   ├── file_writer_tool.py
│   └── diff_tool.py                    ← renamed from code_diff_tool.py
└── prompts/
    ├── ask_mode_prompt.py
    └── agent_mode_prompt.py
```

Five services now own context/prompt concerns instead of two, each single-purpose:
`repository_context_service.py` gathers raw repo facts (files, dependencies, metadata) as
deterministic code; `context_builder_service.py` decides what subset of session state +
repo facts goes into this request; `context_budget_manager.py` enforces the token budget
(input allowance, reserved output, summary-vs-verbatim tradeoffs) that the builder works within;
`prompt_builder_service.py` renders the final provider-agnostic prompt from what the builder
assembled, independent of `ask_mode_prompt.py` / `agent_mode_prompt.py` template content; and
`conversation_history_service.py` owns the raw message log plus running summary. Tool split
rationale: `repository_reader_tool.py` lists/browses repo structure, `file_reader_tool.py` reads
one file's content — conflating the two overloaded a single tool with two responsibilities that
scale differently (browsing is cheap and repo-wide, reading is per-file and content-heavy).

`ai_workspace_repository.py` is the persistence layer (session/message/run rows) that
`agent_session_service.py` and `conversation_history_service.py` sit on top of — keeps DB access
out of the service layer, consistent with `repository_context_service.py` naming but scoped to
storage rather than source-repo scanning (name collision worth double-checking against existing
`worktop/` conventions once real code is available).

Updated: `worktop/main.py` — import and register `ai_workspace_router` under
`{API_PREFIX}/ai-workspace`.

APIs:

```text
GET  /ai-workspace/repositories
GET  /ai-workspace/repositories/{repo_id}/branches
GET  /ai-workspace/repositories/{repo_id}/files
GET  /ai-workspace/repositories/{repo_id}/file-content
POST /ai-workspace/ask                          — read context → ModelClientFactory → answer only, no writes
POST /ai-workspace/agent/run                    — read context → plan → generate changed files → diffs, no writes yet
POST /ai-workspace/agent/apply                  — write only the kept files, ignore rejected
POST /ai-workspace/sessions                     — create session
GET  /ai-workspace/sessions                     — list sessions
GET  /ai-workspace/sessions/{session_id}        — resume session
POST /ai-workspace/sessions/{session_id}/messages — send Ask/Agent message, saved to session
GET  /ai-workspace/sessions/{session_id}/messages — conversation history
```

LLM calls go through the existing `ModelClientFactory` — no new client:

```python
client = ModelClientFactory.get_client(provider, model_config, model_params, db, tenant_id)
input_data = client.prepare_input(system_prompt=system_prompt, user_prompt=user_prompt)
response = client.generate_completion(input_data)
```

### Full file list (33, frozen for V1 beta)

| # | Path | Change |
|---|------|--------|
| 1 | `pages/ai-workspace/ai-workspace.component.ts` | add |
| 2 | `pages/ai-workspace/ai-workspace.component.html` | add |
| 3 | `pages/ai-workspace/ai-workspace.component.scss` | add |
| 4 | `pages/ai-workspace/services/ai-workspace.service.ts` | add |
| 5 | `pages/ai-workspace/models/ai-repository.model.ts` | add |
| 6 | `pages/ai-workspace/models/ai-chat.model.ts` | add |
| 7 | `pages/ai-workspace/models/ai-agent-run.model.ts` | add |
| 8 | `pages/ai-workspace/models/ai-file-change.model.ts` | add |
| 9 | `app.routes.ts` | update |
| 10 | `config/app-constants.ts` | update |
| 11 | `ai_workspace/api/ai_workspace_controller.py` | add (incl. session endpoints) |
| 12 | `ai_workspace/models/ai_workspace_models.py` | add |
| 13 | `ai_workspace/service/ai_workspace_service.py` | add |
| 14 | `ai_workspace/service/ai_agent_orchestrator.py` | add |
| 15 | `ai_workspace/service/repository_context_service.py` | add |
| 16 | `ai_workspace/service/context_builder_service.py` | add |
| 17 | `ai_workspace/service/context_budget_manager.py` | add |
| 18 | `ai_workspace/service/prompt_builder_service.py` | add |
| 19 | `ai_workspace/service/conversation_history_service.py` | add |
| 20 | `ai_workspace/service/agent_session_service.py` | add |
| 21 | `ai_workspace/service/change_planner_service.py` | add |
| 22 | `ai_workspace/service/diff_service.py` | add |
| 23 | `ai_workspace/service/apply_changes_service.py` | add |
| 24 | `ai_workspace/repository/ai_workspace_repository.py` | add |
| 25 | `ai_workspace/tools/repository_reader_tool.py` | add |
| 26 | `ai_workspace/tools/repository_search_tool.py` | add |
| 27 | `ai_workspace/tools/file_reader_tool.py` | add |
| 28 | `ai_workspace/tools/file_writer_tool.py` | add |
| 29 | `ai_workspace/tools/diff_tool.py` | add |
| 30 | `ai_workspace/prompts/ask_mode_prompt.py` | add |
| 31 | `ai_workspace/prompts/agent_mode_prompt.py` | add |
| 32 | `ai_workspace/models/ai_session_models.py` | add |
| 33 | `main.py` | update |

Frontend: 10 files (8 add + 2 update). Backend: 23 files (22 add + 1 update). **Total: 33.**

Deferred past this freeze (not in the 33, no file reserved): `response_chunk_service.py` for
long-response chunking/continuation, background workers, distributed queues, MCP servers,
advanced retrieval infrastructure.

### Context management architecture

This is the part of the design most likely to determine whether the workspace stays usable and
affordable as sessions get long, so it's worth being explicit about now rather than retrofitting
it later. The governing principle: **session state is stored; the prompt is not.** Every
significant request rebuilds a fresh, minimal prompt from stored state rather than replaying
growing conversation history.

```text
User Request
      ↓
Load Session (agent_session_service.py)
      ↓
Gather Context (repository_context_service.py + conversation_history_service.py)
  ├── conversation summary (not full history)
  ├── last ~8–10 messages verbatim
  ├── only the files relevant to this request, not the whole repo
  ├── current task / current plan / prior agent decisions
  └── repository metadata (cached, not re-derived every request)
      ↓
context_builder_service.py selects what goes in, within the budget
context_budget_manager.py enforces the token budget it selects within
prompt_builder_service.py renders the final provider-agnostic prompt
      ↓
ModelClientFactory
      ↓
Tool execution (if Agent mode)
      ↓
Session update (agent_session_service.py + conversation_history_service.py)
```

Concretely, `agent_session_service.py` owns session metadata only (repo, branch, mode, current
task, timestamps) — not the prompt. `conversation_history_service.py` owns the raw message log
plus a running summary that replaces older turns once the recent window fills. Context gathering
itself (files, dependencies, repo metadata) should be deterministic code in
`repository_context_service.py` — no LLM tokens spent until the final prompt is assembled.
`context_builder_service.py` decides *what* goes into a given request (this file, not that one;
summary vs. verbatim history) by calling `context_budget_manager.py`, which owns the token math:
input allowance, reserved output, safety buffer — e.g. of a 128k model context, ~90k input, 8–16k
reserved output, remainder as buffer, never sent in full just because the model supports it.
`prompt_builder_service.py` then renders what the builder assembled into the actual
system/user prompt strings, kept separate so provider-specific prompt formatting doesn't leak
into context-selection logic. Multi-stage reasoning (repo tool finds relevant files → file reader
loads only those → builder assembles prompt → LLM reasons) beats stuffing the whole repository
into one call.

File count for this layer is now settled at 3 services (`context_builder_service.py`,
`context_budget_manager.py`, `prompt_builder_service.py`) — see the file table above.

---

## Final product outcome

A controlled enterprise coding assistant:

```text
Copilot-style Chat
+ Copilot-style Agent
+ Enterprise review controls
+ Backend-driven tools/models
+ Local repository context
+ Existing ModelClientFactory integration
```

That is the V1 definition of done for AI Workspace.

---

## Open questions to resolve before implementation

1. **Need actual file contents** of `app-constants.ts`, `app.routes.ts`, and `main.py` (or
   equivalent excerpts) to produce real edits rather than best-effort snippets matching assumed
   conventions.
2. How does Agent Mode's tool execution get sandboxed against the *local* workspace path — what
   stops `file_writer_tool.py` (or `file_reader_tool.py`) from escaping the selected repo root?
3. Is there an existing SSE pattern elsewhere in `worktop/` to follow, or does this module
   introduce the first one? Event contract (types, ordering, reconnect/resume) needs to match
   whatever `ai-workspace.service.ts` expects to consume.
4. ~~Is `agent/run` → `agent/apply` a two-request flow with server-side staged state~~ — mockup
   confirms Keep/Reject is staged before Apply ("Only kept files will be applied to the
   repository"). Still open: whether that staging lives server-side keyed by run id (frontend
   sends `{ run_id, kept_file_ids }` on Apply) or the frontend round-trips full file content back.
   Server-side staging is the safer default — it means `file_writer_tool.py`'s generated content
   never has to leave the backend until Apply, and the frontend only ever handles diffs for
   display. This determines whether `ai_workspace_repository.py` needs a `runs`/`run_files` table
   alongside `sessions`/`messages`.
5. Does session/chat history persist across repository or branch switches, or is it scoped per
   repo+branch selection? (`agent_session_service.py` metadata includes both, so switching either
   likely means creating/resuming a different session rather than mutating the current one.)
6. What DB/storage does `ai_workspace_repository.py` sit on — same database as the rest of
   `worktop/`, or something session-store-like (Redis) for faster resume? Depends on existing
   `worktop/` infrastructure not yet visible here.
7. Confirm the deferral of `response_chunk_service.py` (see "Deferred past this freeze" above) —
   it was proposed twice in this conversation, the second time in the same message that also said
   "I wouldn't go beyond this for V1." Doc currently treats that as leftover text and excludes it
   from the 33; flag if that's wrong.
8. `context_budget_manager.py`'s token-budget numbers (input allowance, reserved output, safety
   buffer) are illustrative (90k/8–16k on a 128k model) — need real numbers per model tier once
   `ModelClientFactory`'s supported models/context windows are visible.
