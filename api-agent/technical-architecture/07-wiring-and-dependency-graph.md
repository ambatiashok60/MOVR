# Frontend/backend wiring and dependency graph

## Story-to-scenario file wiring

```text
api-test-gen.component.ts/html
 -> api-test-generation.facade.ts
 -> api-test-generation.service.ts
 -> api/routes/api_scenario_routes.py
 -> services/generation_orchestrator.py
 -> services/api_repo_context_service.py + api_repo_profile_service.py
 -> agents/repo_discovery_agent.py + scenario_agent.py
 -> services/api_scenario_generation_service.py
 -> schemas/api_scenario_result.py
 -> service response -> store -> selectors -> api-scenario-table.component.ts/html
```

## Scenario-to-code file wiring

```text
scenario table Generate Code output
 -> facade.generateCode(...)
 -> api-test-generation.service.ts
 -> api/routes/api_test_generation_routes.py
 -> task_managers/api_test_generation_task_manager.py
 -> services/generation_orchestrator.py
 -> discovery tools + strategy_registry.py
 -> mock_stub_planning_service.py
 -> api_test_code_generation_service.py + test_generation_agent.py
 -> generated_file_guard.py + api_test_validator.py + repo_command_validator.py
 -> api_test_file_writer.py + workspace manager
 -> job/events -> facade/store -> mock-plan-review and scenario UI
```

`api-test-generation-events.service.ts` maps to `event_routes.py` and
`api_test_generation_sse_manager.py`. Frontend models under `models/` correspond to Pydantic schemas
under `app/schemas/`; the HTTP service is the only place that should adapt envelope or naming differences.

## Frontend dependency direction

```text
route -> feature container -> facade -> store + service interfaces
feature container -> presentational components + selectors
services -> HTTP/SSE + models
mocks -> service interfaces + production DTO models
presentational components -X-> HTTP services
```

## Repository discovery graph

API Agent does not currently expose a single general-purpose AST graph. It composes specialized static
scanners: `api_endpoint_scanner_tool.py`, `openapi_scanner_tool.py`, `dependency_scanner_tool.py`,
`existing_test_scanner_tool.py`, `fixture_scanner_tool.py`, `mock_stub_scanner_tool.py`,
`source_context_tool.py`, and `command_discovery_tool.py`. `api_repo_context_service.py` and
`api_repo_profile_service.py` normalize this evidence for strategy selection.

Conceptually the graph is:

```text
build/config/source/OpenAPI/test files
 -> scanner facts
 -> nodes: endpoint, controller, client, DTO, test, fixture, dependency, command
 -> edges: handles, calls, serializes, tests, mocks, configures, dependsOn
 -> RepoProfile/SourceContext
 -> strategy + MockStubPlan + generated-file placement
```

This scanner composition is a known limitation versus a compiler-backed Java/Python AST and symbol
resolver. Dynamic Spring beans, reflection, generated clients and runtime discovery require confidence
flags and review. A future graph service should preserve source span, parser, confidence and unresolved
symbol metadata for every edge.

## Safe modification checklist

For a new UI/backend field, update frontend model, service request, facade/store, backend request schema,
route, orchestrator and result mapping together. For a new framework, update scanners/profile evidence,
implement a strategy, register it, add validation/command resolution, mock-plan rules and golden tests.
