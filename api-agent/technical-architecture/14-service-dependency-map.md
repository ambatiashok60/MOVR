# Frontend and backend service dependency map

## Frontend services

| Service | Direct dependencies | Consumers | Responsibility |
|---|---|---|---|
| `ApiTestGenerationFacade` | store, selectors, REST service, event service | `ApiTestGenComponent` | context, run/code workflow, event reduction and terminal refresh |
| `ApiTestGenerationStore` | frontend DTOs | facade, selectors and templates | scenarios, selection, task, events, generated result and errors |
| `ApiTestGenerationSelectors` | store | table/container | derived presentation state |
| `ApiTestGenerationService` | `HttpClient`, API prefix | facade | scenario/code/job/abort/profile REST contracts |
| `ApiTestGenerationEventsService` | browser `EventSource`, API prefix | facade | named task events and stream cleanup |
| `MockApiTestGenerationService` | fixtures, production DTOs | DI | contract-faithful REST preview |
| `MockApiTestGenerationEventsService` | RxJS timers/events | DI | queued/running/progress/terminal preview |
| `FunctionalTestGenerationFacade` | functional store and `TestAgentService` | Functional tab | Test Agent mock/real workflow |

```text
component -> facade -> store/selectors
                  -> REST service -> backend routes
                  -> event service -> SSE route
mock provider ----^ replaces transport only
```

The facade currently refreshes the authoritative job after terminal SSE/error. The target task controller adds
periodic polling, replay cursor, abort handling and stale-context rejection.

## Backend control-plane services

| Service | Direct dependencies | Owns | Called by |
|---|---|---|---|
| `ApiTestGenerationTaskManager` | executor, job models, SSE manager, orchestrator | local task state/transitions | generation/job/abort routes |
| `ApiTestGenerationSseManager` | event schema, buffer/settings | local event buffer/stream format | task manager and event routes |
| `GenerationOrchestrator` | runtime plus generation services | feature-stage ordering/outcome | worker task manager |
| `GenerationRuntime` | tenant/model/workspace context | per-run dependencies/cancellation callbacks | orchestrator/services |

## Backend discovery and decision services

| Service | Direct dependencies | Output consumers |
|---|---|---|
| `ApiRepoContextService` | source/openAPI/endpoint/test scanners | scenario and code generation |
| `ApiRepoProfileService` | dependency/helper/fixture/command scanners | strategy and mock planning |
| `ApiScenarioGenerationService` | scenario agent, repo context, coverage/value | orchestrator and frontend result |
| `TeamTestStrategyService` | repo profile, strategy registry | code plan/review |
| `MockStubPlanningService` | dependency and existing mock evidence | generation agent, validation and review UI |
| `ApiTestCodeGenerationService` | generation agent, source context, strategy/mock plan | generated-file guard/writer |
| `ApiTestFileWriter` | workspace manager, file guard | staged/generated files |
| `ApiCoverageService` | scenarios/generated artifacts | result/review |
| `ReviewReportService` | validation, budget, mock risk | terminal result/UI |
| `TraceabilityService` | story/operation/scenario/file evidence | result/audit |

## Cross-layer service chains

```text
Generate Scenarios:
ApiTestGenerationFacade
 -> ApiTestGenerationService
 -> ApiScenarioRoute
 -> ApiTestGenerationTaskManager
 -> GenerationOrchestrator
 -> ApiRepoContextService + ApiRepoProfileService
 -> ApiScenarioGenerationService
 -> SSE manager / job result
 -> event service + facade/store

Generate Code:
Facade -> REST -> task manager -> orchestrator
 -> profile/context -> TeamTestStrategyService
 -> MockStubPlanningService -> ApiTestCodeGenerationService
 -> file guard/writer -> validators -> review/traceability
 -> job/SSE -> frontend
```

## Service lifetime and replacement

Frontend stores/facades should be scoped to the Test Gen feature when simultaneous contexts are possible; root
scope otherwise risks state leakage across pages. Backend orchestrators/runtimes are per task. Job/event repositories
are application infrastructure and must become durable/shared for multiple processes. Model, DB, tenant, queue,
repository and event implementations are injected adapters. Strategies and scanners are application plugins chosen
from evidence, not global mutable singletons.
