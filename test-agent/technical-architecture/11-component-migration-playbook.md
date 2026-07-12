# Component migration and integration playbook

Test Agent owns backend capabilities rather than an Angular component. Therefore the portable unit is a
backend feature slice plus a host frontend client contract.

## Select the migration unit

Choose one capability: synchronous generation, asynchronous job progress, diff/review presentation, or Apply.
Do not copy a route alone. Its dependency closure includes request/result schemas, orchestrator, selected agents,
inventory/parser services, LLM abstraction, policy/security, validation and configuration.

## Backend dependency closure

```text
generation_routes.py
 -> generation_request.py + generation_result.py
 -> generation_orchestrator.py
 -> runtime/generation_runtime.py
 -> inventory + adapters + agents + prompts
 -> llm abstractions/factory
 -> patching + validation + policy + security
 -> host DB/tenant/model/workspace dependencies
```

Copy project-owned modules in the closure. Replace host-owned dependencies through adapters: authentication,
tenant, DB session, repository registry, model client, task persistence, audit and notifications. Never copy
standalone placeholder dependencies into production as if they were platform implementations.

## Host frontend slice

Create `TestAgentClient`, DTO models, an API adapter, optional SSE adapter, facade/store and presentation
components. Map backend snake/camel/envelope differences once in the API adapter. The component should receive
story/repository/branch as inputs and emit generation/review actions rather than reading host global state.

## Migration order

1. Copy contracts and compile them in isolation.
2. Register backend routes and replace host dependency providers.
3. Copy/configure the client adapter and base URL.
4. Add facade/store and then presentation components.
5. Wire job/SSE reconciliation if asynchronous execution is enabled.
6. Add review authorization and transactional Apply through host services.
7. Run schema, route, generation, validation and UI contract tests.

## Completion gate

The migration is complete only when a real request crosses the host component/client, route, orchestrator and
validator; errors and terminal states render correctly; tenant/repository authorization is enforced; mocks can
be replaced only through DI; and no original-repository import remains unresolved.
