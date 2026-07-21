# Dependency graphs (api-agent)

Three primary graph views over one underlying typed-node / typed-edge model.
Together they give end-to-end application impact:

```text
Backend implementation  →  API contract  →  Frontend API consumption  →  Frontend implementation
```

- [01 — Backend Code Dependency Graph](01-backend-code-graph.md)
- [02 — Cross-Layer Contract Propagation Graph](02-cross-layer-contract-graph.md)
- [03 — Frontend Code Dependency Graph](03-frontend-code-graph.md)

These are **views**, not separate databases: import, call, class, DTO/entity,
DB, test, and module concerns are all expressed as typed edges in the same
model, filtered per view.

## Node types

| Node | Meaning (api-agent) |
|---|---|
| `FILE` | a source module |
| `CLASS` | a class / agent / service / guard |
| `METHOD` | a significant method (stage entrypoint) |
| `API` | an HTTP endpoint (REST) or SSE stream |
| `DTO` | a request/response/schema model (Pydantic or TS interface) |
| `ENTITY` | a persisted domain entity — **none exist in api-agent** (see 02/16) |
| `TABLE` | a database table — **none owned by api-agent** |
| `COMPONENT` | an Angular component |
| `STORE` | an Angular signal store / facade / selectors |
| `SERVICE` | a frontend Angular service (HTTP/SSE transport) |
| `TEST` | a unit/integration/e2e test |
| `EXTERNAL` | a Worktop symbol or infrastructure dependency |

## Relationship (edge) types

| Edge | Meaning |
|---|---|
| `IMPORTS` | file imports file |
| `CALLS` | method/class invokes another |
| `IMPLEMENTS` | class implements interface/base |
| `CONSTRUCTS` | class instantiates a dependency (DI seam) |
| `ACCEPTS` / `RETURNS` | endpoint/method input/output DTO |
| `EXPOSES` | controller exposes an endpoint |
| `CONSUMES` | frontend service consumes an endpoint |
| `MAPS_TO` | DTO maps to another DTO/entity |
| `PERSISTS_TO` | writes/reads a table/entity (only the model-config DAO here) |
| `RENDERS` | component renders child component |
| `BINDS_TO` | component binds to its template |
| `USES` | component uses a service/store |
| `TESTED_BY` | production node covered by a test |
| `DEPENDS_ON` | module/infra dependency |

> **Persistence note:** api-agent defines no ORM entities or tables. The only
> `PERSISTS_TO`/`EXTERNAL` DB edge is model-config lookup by `tenant_id`. Full
> reasoning in [16-integration-persistence-and-dependency-graph.md](../16-integration-persistence-and-dependency-graph.md).
