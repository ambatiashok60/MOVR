# Dependency graphs (test-agent)

Three primary graph views over one typed-node / typed-edge model, giving
end-to-end impact:

```text
Backend implementation  →  API contract  →  Frontend API consumption  →  Frontend implementation
```

- [01 — Backend Code Dependency Graph](01-backend-code-graph.md)
- [02 — Cross-Layer Contract Propagation Graph](02-cross-layer-contract-graph.md)
- [03 — Frontend Code Dependency Graph](03-frontend-code-graph.md)

test-agent generates **Playwright E2E** specs. Unlike api-agent it is
**synchronous**: `POST /api/playwright/generate` runs the whole orchestrator
inline (no task-manager queue in the hot path). Scope of the frontend view: the
**functional-test-gen tab** (which physically lives in the api-agent frontend
tree but consumes `/api/playwright`).

## Node types

`FILE`, `CLASS`, `METHOD`, `API`, `DTO`, `ENTITY` (**none — no ORM**), `TABLE`
(**none owned**), `COMPONENT`, `STORE`, `SERVICE`, `TEST`, `EXTERNAL`.

## Relationship (edge) types

`IMPORTS`, `CALLS`, `IMPLEMENTS`, `CONSTRUCTS`, `ACCEPTS`, `RETURNS`, `EXPOSES`,
`CONSUMES`, `MAPS_TO`, `PERSISTS_TO` (only the model-config DAO), `RENDERS`,
`BINDS_TO`, `USES`, `TESTED_BY`, `DEPENDS_ON`.

> **Persistence note:** like api-agent, test-agent defines no ORM entities/tables.
> The only DB edge is model-config lookup by `tenant_id` in the LLM adapter.
> It also writes generated specs to the workspace on disk (files, not a DB).
