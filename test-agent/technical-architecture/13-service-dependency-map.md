# Frontend and backend service dependency map

## Frontend client-service boundary

Test Agent has no native standalone host page. The portable Functional Tests slice currently resides under
`api-agent/frontend/test-generation/functional-test-gen` and uses this runtime chain:

```text
FunctionalTestGenComponent
 -> FunctionalTestGenerationFacade
 -> FunctionalTestGenerationStore
 -> TestAgentService
 -> HTTP /api/playwright/*

preview DI:
TestAgentService token -> MockTestAgentService -> fixture models
```

| Frontend service | Direct dependencies | Consumers | Contract/lifecycle |
|---|---|---|---|
| `FunctionalTestGenerationFacade` | store, `TestAgentService`, story context | Functional component | feature workflow; page/feature lifetime preferred |
| `FunctionalTestGenerationStore` | functional DTO models | facade and template | signal state; must reset on context revision |
| `TestAgentService` | Angular `HttpClient`, API prefix | facade | synchronous mock today; target async task contract |
| `MockTestAgentService` | fixtures, production DTOs | DI provider | preview-only service replacement |

The target async architecture adds `TestAgentEventsService`, `TestAgentTaskController` and polling reconciliation;
the component remains dependent on the facade only.

## Backend service graph

| Backend service | Direct dependencies | Produces/owns | Primary consumers |
|---|---|---|---|
| `GenerationOrchestrator` | runtime, discovery, decision, patch, validation and result services | complete generation transaction | generation route/future task handler |
| `TechnologyIntelligenceService` | adapters, repo evidence | technology profile | orchestrator, strategy services |
| `SourceIntelligenceService` | parsers, dependency map | source mapping | placement/ownership/locator decisions |
| `InventoryService` | inventory builder/cache/reader | repository inventory | most discovery and decision stages |
| `BehavioralInventoryService` | parsed tests/source intelligence | behavioral units/coverage evidence | action, merge, placement |
| `PlaywrightUiIntelligenceService` | Angular/Playwright evidence | UI/locator context | locator and generation logic |
| `SpecPlacementService` | candidate ranking agent, inventory | destination decision | orchestrator/code generation |
| `OwnershipResolutionService` | ownership agent, graph evidence | owner/helper boundary | placement and patch planning |
| `TestActionService` | action agent, existing coverage | create/update/skip | flow merge/generation |
| `FlowMergeService` | merge agent, behavioral units | merged/separate flow plan | generation |
| `CodeGenerationService` | generation agent, prompts, decisions | structured code patch | patch planner |
| `RepositoryPolicyService` | settings/policy schema | allowed scope/commands | discovery, patching, execution |
| `DataGovernanceService` | redaction/restricted-path rules | safe evidence | tools, prompts, logs |
| `ResultBuilderService` | decisions, validation, coverage and review | `GenerationResult` | route/frontend client |

## Service interaction rules

Services exchange typed schemas, never mutable global dictionaries. Discovery services are read-only and reusable.
Decision services may call model agents but cannot write. Patch services mutate only an authorized isolated workspace.
Validation services consume a patch and evidence; they cannot redefine intent. The orchestrator owns ordering and
terminal outcome. Future task services own scheduling/status but cannot decide generation success independently.

## Cross-boundary contract map

```text
Frontend Generate Test Cases
 -> scenario request DTO
 -> future Test Agent scenario task handler
 -> functional testcase DTOs
 -> frontend store/table

Frontend Generate Code
 -> GenerationRequest
 -> GenerationOrchestrator
 -> GenerationResult + validation/review
 -> frontend store/drawer
```

Until the scenario endpoint and asynchronous job manager are implemented in Test Agent, the first chain is mock-only
and the code-generation chain adapts the synchronous `/generate` endpoint.
