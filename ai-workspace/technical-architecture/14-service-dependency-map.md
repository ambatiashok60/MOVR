# Frontend and backend service dependency map

## Frontend service registry

| Service | Direct dependencies | Consumers | Responsibility |
|---|---|---|---|
| `AiWorkspaceFacade` | store and all workflow services | page/container components | orchestration of bootstrap, context, Ask/Agent, review and settings |
| `AiWorkspaceStore` | frontend models | facade, selectors, components | authoritative page state |
| `BootstrapService` | HTTP | facade | initial repositories/models/tools/runtime |
| `WorkspaceService` | HTTP | facade/workspace components | validate path, repositories, branches and files |
| `ContextBuilderService` | HTTP | facade/context components | selected and priority context |
| `SessionService` | HTTP | facade/session components | session create/list/resume |
| `ConversationService` | HTTP | facade/conversation | messages/history |
| `AiWorkspaceService` | HTTP | facade | Ask and compatibility Agent entry points |
| `AgentService` | HTTP | facade | start run and fetch plan |
| `ExecutionService` | HTTP | target task controller/facade | status, cancel and retry contracts |
| `SseService` | EventSource | target task controller/facade | execution events |
| `ReviewService` | HTTP | facade/review panel | keep/reject/summary/Apply |
| `ModelRegistryService` | HTTP | facade/settings | catalog/runtime model selection |
| `ToolRegistryService` | HTTP | facade/settings | catalog/runtime tool selection |

Current gap: `ExecutionService` and `SseService` exist but do not drive `submitPrompt`; Agent mode waits for the
start request to complete. The shared task controller will become their single consumer and update the store.

## Backend service registry

| Application service | Direct dependencies | Output/consumers |
|---|---|---|
| `ExecutionOrchestrator` | chat/agent services, execution/event stores | routes, execution DTOs |
| `ChatService` | context builder, prompt/LLM services, message/session stores | Ask response/history |
| `AgentService` | context, prompts, tools, repository staging, patch validation, review | Agent execution/plan/files |
| `ContextBuilderService` | repository reads/search/tree, selected context, memory | chat/agent prompts |
| `RepositoryMemoryService` | state store/repository evidence | context builder and summaries |
| `ToolSelectionService` | tool definitions, plan/evidence | Agent next action |
| `ToolExecutionService` | registry, policy/runtime | observations/events |
| `ToolRegistry` | concrete read/search/list/test/write/diff/apply tools | selection/execution |
| `PatchValidationService` | repository/command/diff services | Agent repair/review |
| `ReviewService` | review store, transaction service | review routes/Apply |
| `EngineeringReviewService` | diff/validation/evidence | review score/report |
| `WorkspaceRuntimeService` | runtime store | bootstrap/session/execution |
| `SessionService` | session/message/state stores | session routes/frontend |
| `ModelCatalogService` | configuration/runtime store | model routes/settings UI |
| `ToolCatalogService` | registry/runtime store | tool routes/settings UI |

## Repository services

```text
ContextBuilder/Tools
 -> RepositoryAccessService
 -> FileReadService / RepositorySearchService / RepositoryScanService
 -> RepositoryTreeService / GitDiffService
 -> local repository + Git providers

Agent staged mutation
 -> IsolatedWorkspaceService
 -> FileWriteService
 -> PatchValidationService
 -> WorkspaceTransactionService
 -> lock + hash verification + journal + rollback
```

Repository services expose application operations; concrete filesystem/Git providers are infrastructure and must
not leak into Agent decisions.

## LLM service chain

```text
ChatService/AgentService
 -> LlmApplicationService
 -> LlmGateway / LlmStreamService
 -> LlmClientFactory
 -> DefaultLlmClientAdapter OR explicit MockLlmClient
 -> Worktop model gateway
 -> LlmTelemetryService + ReviewBudgetService
```

Mock selection is configuration-controlled. Production failure to create a real model client must fail explicitly.

## State and event dependencies

```text
application services
 -> StateStore abstractions
 -> in-memory (preview) | SQLite (local durable) | MySQL (platform durable)

ExecutionEventService
 -> SseEventPublisher
 -> SSE route
 -> frontend SseService
```

The current publisher is process-local. The target shared task/event repositories become authoritative, with SSE
as notification and polling as reconciliation. Execution status, plan, review and events must share task identity
and repository revision.

## Complete Ask and Agent service chains

```text
Ask:
component -> facade -> AiWorkspaceService
 -> ai_workspace_routes -> ExecutionOrchestrator -> ChatService
 -> ContextBuilderService -> LLM services -> message/session stores
 -> response -> store -> conversation components

Agent target:
component -> facade -> shared TaskController -> AgentService/ExecutionService/SseService
 -> run route -> dispatcher/worker -> ExecutionOrchestrator -> AgentService
 -> context -> tool selection/execution -> isolated workspace -> validation/review
 -> durable task/events -> SSE/polling -> store -> plan/timeline/diff/review components
```

## Dependency-lifetime rules

Page state/facades are feature-scoped; transport clients may be application singletons. Execution orchestrators and
runtimes are per task. DB sessions are created per request/worker unit and never passed unsafely into another thread.
Task/event stores and distributed leases are application-scoped durable infrastructure. Repository transactions are
per Apply operation. Model/tool runtime selection is tenant/session scoped and versioned with the execution.
