# Integration: persistence, ORM, and cross-service dependency graph

Purpose: the concrete technical picture an engineer needs to lift these
components into the real WorkTop app — what the frontend actually calls, which
backend owns it, where state lives, and exactly where (and how little) the
database is touched. This complements the code-import graphs in
`13-internal-external-dependency-graphs.md` and `14-service-dependency-map.md`
with the **persistence / ORM / integration-seam** reality those docs leave
abstract.

---

## 1. Headline: there is no ORM, and generation is stateless

Neither backend defines a single ORM model. Verified: no `__tablename__`,
`declarative_base`, `Column(`, `Mapped[`, or `relationship(` anywhere in
`api-agent/worktop/**` or `test-agent/worktop/**`.

- **Generation pipelines are pure functions over a repository on disk.** Input:
  request + repo path. Output: generated files written to the workspace +
  a result DTO. No entities, no migrations, no persistence of domain data.
- **The only database dependency is model-configuration lookup**, keyed by
  `tenant_id`, performed inside the LLM adapter (see §4). The DB answers one
  question: "which model/provider/params should this tenant use?"
- **Job and event state is in-memory** (Python dicts/deques), not persisted
  (see §5). This is the single biggest thing integration must replace.

Implication for WorkTop integration: you are not merging a data model or ORM
layer. You are wiring (a) an injected DB session used only for model config,
(b) a durable job/event store to replace the in-memory one, and (c) the HTTP +
SSE routes behind WorkTop's envelope.

---

## 2. Frontend → backend endpoint map (the frontend talks to TWO backends)

The Test Gen frontend is not a single-backend client. The API-test tab targets
**api-agent**; the functional (Playwright) tab targets **test-agent**.

| Frontend service | Prefix | Backend | Endpoints (method path) |
|---|---|---|---|
| `ApiTestGenerationService` | `/api/api-test-generation` | **api-agent** | `POST /generate-api-scenarios`, `POST /generate-api-test-code`, `GET /jobs/{id}`, `POST /abort/{id}`, `POST /checkRepoProfile`, `POST /generateRepoProfile` |
| `ApiTestGenerationEventsService` | `/api/api-test-generation` | **api-agent** | `GET /events/{id}` (SSE, `EventSource`) |
| `TestAgentService` (functional tab) | `/api/playwright` | **test-agent** | `POST /scenarios`, `POST /generate` |

```text
Test Gen UI
 ├─ API tab      → ApiTestGenerationService  → /api/api-test-generation/*  → api-agent (FastAPI)
 │                 ApiTestGenerationEvents(SSE)→ /api/api-test-generation/events/{id}
 └─ Functional   → TestAgentService          → /api/playwright/*           → test-agent (FastAPI)
```

Integration checkpoints:
- Both prefixes must be routed to the correct service behind WorkTop's gateway.
- **Verify endpoint parity:** the functional frontend calls `POST /api/playwright/scenarios`,
  but the test-agent backend currently exposes `POST /api/playwright/generate`
  (+ `/jobs/{id}`, `/events/{id}`). Confirm/align the `/scenarios` route before
  wiring the real (non-mock) `TestAgentService`.
- Mock providers (`provideApiTestGenerationMocks`, `provideTestAgentMocks`)
  replace **only the service classes** — swapping to real HTTP is a one-line DI
  change per tab, no component edits (see §6).

---

## 3. Backend dependency chain (per request, both backends)

```text
HTTP route  (WorkTop supplies db + tenant_id via DI)
  → TaskManager            (in-memory job registry + executor)      [api-agent]
  → GenerationOrchestrator (stage ordering, abort checks)
  → GenerationRuntime.create(db, tenant_id, repo_path, branch)
      → LLM client factory / adapter  (db, tenant_id)  ── the only DB consumer
  → discovery/decision services (repo scan, scenario/code agents, guards)
  → file writer  → workspace on disk
  → SseManager (in-memory event buffer)  → SSE route → frontend EventSource
```

test-agent is the same shape without the task-manager queue in the hot path:
`POST /api/playwright/generate` → `GenerationOrchestrator.generate(request)` →
`GenerationRuntime.from_request(request, db)` → `LLMClientFactory.create(db,
tenant_id)` → agents/guards → scoped patch writer.

---

## 4. The database dependency (all of it)

DB access is confined to the LLM adapter, reached only through the runtime.

**api-agent** — `WorktopModelClientAdapter(db, tenant_id)`:
- Primary path: `DefaultLLMClient(db=db, tenant_id=tenant_id)` (Worktop resolves
  model config internally).
- Fallback path (`_create_direct_model_client`): explicit lookups —
  - `CommonUtils.load_model_info(self.db, self.tenant_id)` → model params
  - `ModelsConfigurationDAO(self.db).get_model_config_by_tenant_id(self.tenant_id)`
    → provider/model config

**test-agent** — `LLMClientFactory.create(db, tenant_id)` → `DefaultLLMClientAdapter`
wrapping Worktop's `DefaultLLMClient(db, tenant_id)`. Same single purpose.

```text
db (SQLAlchemy session, injected by WorkTop)
 └─ tenant_id ─┬─ DefaultLLMClient(db, tenant_id)                 [primary]
               └─ ModelsConfigurationDAO(db).get_model_config_by_tenant_id(tenant_id)
                  CommonUtils.load_model_info(db, tenant_id)      [fallback]
```

That is the complete DB surface. There is no read/write of scenarios, tests,
jobs, or coverage to any database — those live in memory (§5) or on disk
(generated files). `tenant_id` is mandatory: without it the real LLM client
cannot be created and generation fast-fails (by design — no silent placeholder
model).

---

## 5. In-memory state that MUST become durable for integration

| State | Where | Type | Integration action |
|---|---|---|---|
| Job registry | `ApiTestGenerationTaskManager._jobs` | `dict[str, GenerationJob]` | Replace with a shared/durable store (DB table or Redis) for multi-process / multi-replica serving |
| Idempotency map | `ApiTestGenerationTaskManager._key_to_task_id` | `dict[str, str]` | Same store; needed so retries and replays survive process restarts |
| Event buffers | `ApiTestGenerationSseManager._buffers` | `defaultdict[str, deque]` (maxlen `settings.max_event_buffer`) | Replace with a shared pub/sub or event table so SSE works across replicas |

Consequence: as-is, both services are **single-process**. A job created on one
worker is invisible to another. For WorkTop's multi-instance deployment, the
task manager and SSE manager are the two adapters to reimplement against durable
infrastructure — the interfaces are already isolated (they are injected into the
orchestrator/routes), so this is a targeted swap, not a rewrite.

> The **target** durable design — `TaskRepository`/`EventRepository` protocols,
> the proposed `task`/`task_event`/`task_attempt`/`repository_lease`/
> `task_artifact` relational model, and ORM/session rules — is specified in
> `15-task-frontend-persistence-portability.md`. This section documents only the
> **current** in-memory reality and which two components to replace; §4 above is
> the separate (and only) DB dependency that exists today.

---

## 6. Frontend dependency graph (files → services → transport)

```text
component (api-test-gen / functional-test-gen)
  → facade (workflow orchestration)
      → store (signals: scenarios, task, events, result, errors)
      → selectors (derived view state)
      → REST service ───────────────→ HTTP  → backend routes
      → events service ─────────────→ SSE   → backend event route
  mock provider ──replaces service class only──^  (fixtures depend on prod models;
                                                   prod components never import fixtures)
```

DI seams (the only edits to go from preview → real backend):
- `provideApiTestGenerationMocks()` → remove ⇒ real `ApiTestGenerationService` +
  `ApiTestGenerationEventsService` (HttpClient) take over.
- `provideTestAgentMocks()` → remove ⇒ real `TestAgentService`.
- `providePrimeNG({ theme: WorktopPreset })` → at integration, inherit WorkTop's
  own theme instead of the preview preset.
- Path alias `@api-test-generation/*` → `api-agent/frontend/test-generation/*`
  (tsconfig `paths`) must be reproduced or the sources relocated into the host.

Presentational components (tables, drawers, timelines) depend on **models and
`@Input`/`@Output` only** — no HTTP/SSE — so they port unchanged.

---

## 7. External WorkTop dependency surface (what the host must provide)

Lazy-imported (so the services import and unit-test standalone; these resolve
only at runtime inside WorkTop):

| Symbol | Module | Used for |
|---|---|---|
| `DefaultLLMClient` | `worktop.core_services.app.gen_ai_models.default_llm_client` | primary model client |
| `ModelClientFactory` | `worktop.core_services.app.gen_ai_models.model_client_factory` | direct model client (fallback) |
| `ModelsConfigurationDAO` | `worktop.core_services.app.dao.models_config_dao` | tenant model config (the one DAO) |
| `CommonUtils` | `worktop.core_services.app.utility.common_utils` | tenant model params |
| custom logger | `worktop.core_services.app.utility.custom_logger.*` | standardized logging |

Everything else (FastAPI, Pydantic, scanners, agents, strategies, guards) is
self-contained in the package.

---

## 8. Integration seam checklist

1. **DB session provider** — inject WorkTop's SQLAlchemy session as `db` at the
   route boundary; it flows unchanged to the LLM adapter. No schema/migration.
2. **Tenant context** — supply `tenant_id` on every request (JWT/session);
   generation fast-fails without it.
3. **Durable job + event store** — replace `TaskManager._jobs` /
   `_key_to_task_id` and `SseManager._buffers` (§5).
4. **Route envelope** — wrap both prefixes (`/api/api-test-generation`,
   `/api/playwright`) with WorkTop's API envelope + JWT/permission guards.
5. **Workspace path resolution** — point the file writer/path-safety at
   WorkTop's local workspace root convention.
6. **Frontend DI** — drop the two mock providers; keep the real services; align
   theme to the host. Verify the `/api/playwright/scenarios` route parity (§2).
7. **No ORM work** — there is no data model to merge; do not look for one.
