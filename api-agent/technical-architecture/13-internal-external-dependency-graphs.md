# Internal and external dependency graphs

## Frontend internal graph

```text
test-generation.component.ts/html
 -> functional-test-gen/functional-test-gen.component.*
 -> api-test-gen/api-test-gen.component.*

api-test-gen.component.ts
 -> components/api-scenario-table/*
 -> components/mock-plan-review/*
 -> store/api-test-generation.facade.ts

api-test-generation.facade.ts
 -> store/api-test-generation.store.ts
 -> store/api-test-generation.selectors.ts
 -> services/api-test-generation.service.ts
 -> services/api-test-generation-events.service.ts
 -> models/api-scenario*.ts
 -> models/api-test-generation.model.ts

functional-test-gen.component.ts
 -> functional-test-gen/store/functional-test-generation.facade.ts
 -> functional-test-gen/store/functional-test-generation.store.ts
 -> functional-test-gen/services/test-agent.service.ts
 -> functional-test-gen/models/functional-test-generation.model.ts
```

Mock providers replace service classes only. Fixtures depend on production models; production components never
import fixtures. Presentational tables/drawers depend on models and inputs/outputs, not HTTP or SSE.

## API Agent backend graph

```text
app/main.py
 -> api/routes/api_scenario_routes.py
 -> api/routes/api_test_generation_routes.py
 -> api/routes/job_routes.py
 -> api/routes/event_routes.py
 -> api/routes/repo_profile_routes.py

generation routes
 -> schemas/request/result/job/event
 -> task_managers/api_test_generation_task_manager.py
 -> task_managers/api_test_generation_sse_manager.py
 -> services/generation_orchestrator.py

generation_orchestrator.py
 -> runtime/generation_runtime.py
 -> services/api_repo_context_service.py
 -> services/api_repo_profile_service.py
 -> services/api_scenario_generation_service.py
 -> services/team_test_strategy_service.py
 -> strategies/strategy_registry.py
 -> services/mock_stub_planning_service.py
 -> services/api_test_code_generation_service.py
 -> services/api_test_file_writer.py
 -> coverage/api_coverage_service.py
 -> validation/*
 -> services/review_report_service.py
 -> services/traceability_service.py
```

## Discovery and strategy graph

```text
api_repo_context/profile services
 -> tools/repo_explorer.py
 -> tools/api_endpoint_scanner_tool.py
 -> tools/openapi_scanner_tool.py
 -> tools/dependency_scanner_tool.py
 -> tools/existing_test_scanner_tool.py
 -> tools/fixture_scanner_tool.py
 -> tools/mock_stub_scanner_tool.py
 -> tools/source_context_tool.py
 -> tools/command_discovery_tool.py
 -> schemas/RepoProfile + SourceContext + RepoUnderstanding

RepoProfile + scenario target
 -> strategy_registry.py
 -> java_spring_rest_assured_strategy.py
 -> java_spring_mockmvc_strategy.py
 -> python_pytest_httpx_strategy.py
 -> python_fastapi_testclient_strategy.py
 -> placement + command + validator decisions
```

## Task and event runtime graph

```text
frontend Generate action
 -> REST service
 -> route
 -> task manager
 -> ThreadPoolExecutor
 -> GenerationOrchestrator
 -> job mutation + SSE manager publish
 -> event route/EventSource
 -> frontend facade/store
 -> terminal GET job reconciliation
```

This task/event state is currently in process memory and therefore cannot cross processes or survive restart.
The shared async plan replaces concrete storage/executor dependencies with repositories and a dispatcher.

## External dependency graph

| External dependency | Consumers | Boundary/concern |
|---|---|---|
| Angular/TypeScript/RxJS | portable frontend | host version compatibility |
| PrimeNG/PrimeIcons | UI templates/styles | host component API/theme |
| Browser EventSource | SSE service | cookies only; bearer auth needs fetch-SSE adapter |
| FastAPI/Pydantic | backend routes/contracts | platform router/envelope adaptation |
| Worktop DB/tenant/auth | routes/model creation | injected host dependencies |
| Worktop model client | LLM adapter | model-client interface/factory |
| Java/Gradle/Maven/Spring test stacks | target repositories | strategy and command adapters |
| Python/pytest/httpx/FastAPI TestClient | target repositories | strategy and command adapters |
| Docker/Testcontainers/WireMock | optional test infrastructure | MockStubPlan + execution policy |
| Git/filesystem | discovery and mutation | workspace manager/locks/journal |
| queue/Redis/Valkey/DB | future durable jobs/events | TaskRepository/EventRepository/Dispatcher |

## Coupling constraints

Frontend components cannot import backend concepts beyond DTO models. Facades own workflow, stores own state,
services own transport. Routes cannot contain generation strategy logic. Strategies cannot publish UI events
directly; the task runtime translates progress. Scanners cannot write files. Model agents cannot bypass file guards,
workspace locks or validators. External infrastructure must be behind an interface and must expose timeout,
cancellation, telemetry and failure classification.
