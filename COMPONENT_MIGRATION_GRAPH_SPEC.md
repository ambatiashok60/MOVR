# Component migration dependency-graph specification

## Purpose

This specification defines the minimum dependency intelligence required to move one frontend component or feature
slice into another repository without discovering missing contracts, providers, styles or backend behavior only
after compilation. It uses one typed graph with three primary views:

1. Backend Code Dependency Graph
2. Cross-Layer Contract Propagation Graph
3. Frontend Code Dependency Graph

Runtime infrastructure is represented with typed nodes/edges in the same graph and exposed as an optional view.

## Unified graph model

Every node has `id`, `type`, `name`, `repository`, `path`, optional source span, language/framework, version,
visibility and metadata. Every edge has `type`, source, target, evidence, confidence, resolution status, producer,
repository revision and last validation time.

Recommended node types:

```text
FILE MODULE PACKAGE CLASS INTERFACE METHOD FUNCTION
ROUTE CONTROLLER SERVICE REPOSITORY CLIENT CONFIG PROVIDER
DTO FIELD ENTITY TABLE COLUMN MIGRATION
COMPONENT TEMPLATE STYLE TOKEN STORE SELECTOR PIPE DIRECTIVE
API EVENT TOPIC TASK WORKER TEST COMMAND ENVIRONMENT
```

Recommended relationship types:

```text
IMPORTS EXPORTS DECLARES IMPLEMENTS EXTENDS CALLS INJECTS PROVIDES
EXPOSES ACCEPTS RETURNS EMITS CONSUMES MAPS_TO SERIALIZES_AS
PERSISTS_TO READS_FROM WRITES_TO MIGRATED_BY
ROUTES_TO LOADS RENDERS BINDS_TO STYLED_BY USES_TOKEN
SELECTS_FROM DISPATCHES TESTED_BY VALIDATED_BY CONFIGURED_BY
PUBLISHES SUBSCRIBES_TO EXECUTED_BY REQUIRES_PACKAGE REQUIRES_ENV
```

Dynamic edges from DI, reflection, generated clients, route configuration or runtime discovery must be retained as
`inferred` or `unresolved`; they must not be silently promoted to compiler-proven relationships.

## View 1 — Backend Code Dependency Graph

This view begins at the backend endpoint/task handler used by the component and includes controllers/routes,
application services, repositories, external clients, task managers, workers, schemas, domain objects, persistence,
configuration and tests.

```text
route -> request DTO -> application service -> repository/client
      -> response DTO -> mapper -> domain/entity -> table/migration
      -> task manager -> worker -> events/status
      -> unit/integration/contract tests
```

A backend migration closure is incomplete if it excludes an injected provider, mapper, table/migration, task/event
store, authorization dependency, configuration key or validation test required by the endpoint.

## View 2 — Cross-Layer Contract Propagation Graph

This is the most important migration bridge.

```text
backend route/method
 -> accepts backend request DTO
 -> returns backend response DTO
 -> emits task/SSE/event DTO
 -> frontend transport method
 -> frontend model/mapper
 -> facade/store/selector
 -> component input/display/action
```

### DTO field propagation record

Every field crossing a boundary must have a row like:

| Source | Field | Wire name/type | Frontend target | Transformation | Required/default | Consumers |
|---|---|---|---|---|---|---|
| `GenerationJob` | `task_id` | `task_id:string` | `GenerationJob.taskId` | snake→camel mapper | required | facade, SSE reconciliation |
| `TaskEvent` | `status` | enum string | `ExecutionStatus` | enum normalization | required | store, Run/Abort buttons |
| `FileChangeDto` | `diff` | string | `FileChange.diff` | none | optional empty | diff viewer |

For each DTO document:

- Backend schema/model and file
- Endpoint/event using it
- Serialization aliases and envelope
- Nullable versus missing semantics
- Enum mappings and terminal values
- Date/time and timezone representation
- Numeric precision/ID representation
- Defaulting and compatibility rules
- Frontend model and mapper
- Store/selectors/components consuming each field
- Contract and fixture tests

Changing a DTO field requires graph traversal to all `CONSUMES`, `MAPS_TO`, `BINDS_TO` and `TESTED_BY` consumers.

## View 3 — Frontend Code Dependency Graph

Begin at the selected component and compute both compile-time and runtime closure:

```text
route -> page/container -> component.ts -> template + style
component -> child/shared components + directives + pipes
component -> facade -> store/selectors -> services -> models/mappers
service -> HttpClient/EventSource -> API/event contract
app config -> DI providers/tokens/interceptors/guards
workspace config -> tsconfig aliases/package/style/theme/assets
component/flow -> unit/component/E2E tests
```

The graph must distinguish component `imports` from DI `providers`. Angular templates create dependencies not
visible from TypeScript call graphs: selectors, pipes, directives, event outputs, input bindings, CSS classes,
global theme tokens and assets all belong in the closure.

## Component migration manifest

Every migrated component/feature should have a machine-readable manifest containing:

```yaml
component: ApiTestGenComponent
source_repository: api-agent
source_root: frontend/test-generation/api-test-gen
target_route: /test-generation/api-tests
files:
  - source: api-test-gen/api-test-gen.component.ts
    classification: copy
  - source: services/api-test-generation.service.ts
    classification: replace-adapter
packages:
  - name: '@angular/core'
    source_range: '^18.2'
    target_compatibility: verified
providers:
  - token: ApiTestGenerationService
    implementation: WorktopApiTestGenerationService
contracts:
  - endpoint: POST /api/api-test-generation/generate-api-scenarios
    request: GenerateApiScenariosRequest
    response: QueuedTask
styles:
  - type: global-token
    name: --surface-border
verification:
  - build
  - component-contract-test
  - real-backend-smoke-test
```

Classifications are `copy`, `host-provided`, `replace-adapter`, `package`, `configuration`, `asset`, `generated`,
or `demo-only`. Each `replace-adapter` item must name the target implementation and compatibility test.

## Migration closure algorithm

1. Select component or route root.
2. Traverse frontend compile edges: imports, template declarations, child selectors, pipes, directives and styles.
3. Traverse runtime frontend edges: DI providers, tokens, guards, interceptors, stores and configuration.
4. Follow service methods through API/event contracts.
5. Traverse backend request/response/event DTOs field by field.
6. Follow backend route to service, repository/client, task/worker and persistence/infrastructure dependencies.
7. Include tests, fixtures, packages, assets, environment variables and migrations.
8. Classify every node for copy/replace/host ownership.
9. Detect target collisions, version incompatibilities and unresolved dynamic edges.
10. Generate an ordered migration plan and verification suite.

## Compatibility rules

A component is portable only when:

- All relative and alias imports resolve in the target.
- Angular/framework/package versions are compatible.
- Every selector, pipe and directive used by the template is imported.
- Every injected token/provider is registered at the intended lifetime.
- Global styles, variables, icons and assets exist or are adapted.
- DTO wire names, nullability, enums and date formats are compatible.
- Every HTTP/SSE/event operation maps to a mounted, authorized backend contract.
- Task states and terminal events match frontend Run/Abort logic.
- ORM/database replacement preserves repository contracts and migrations.
- Mock and real providers satisfy the same contract tests.
- Unresolved dynamic dependencies are reviewed explicitly.

## Required migration documentation output

For each portable component or feature, generate:

1. Component overview and responsibility
2. Frontend dependency closure
3. Cross-layer DTO propagation matrix
4. Backend service/task/persistence closure
5. External package/runtime dependency table
6. Copy/replace/host-provided manifest
7. Ordered wiring steps
8. Mock-to-real replacement guide
9. Compatibility risks and unresolved edges
10. Build, contract, integration and end-to-end acceptance tests

The three graph views remain the canonical architecture. DTO, persistence, worker, infrastructure and test graphs
are filtered views or typed subgraphs—not separate competing sources of truth.

Shared files, visual assets, generated resources, platform utilities and test resources follow
[`SHARED_RESOURCES_MIGRATION_SPEC.md`](SHARED_RESOURCES_MIGRATION_SPEC.md).
