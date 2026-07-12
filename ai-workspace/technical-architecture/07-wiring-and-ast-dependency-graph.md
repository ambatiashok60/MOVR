# Frontend/backend wiring and AST dependency graph

## Application bootstrap and navigation

```text
main.ts -> app.config.ts -> app.routes.ts
 -> layout/main-layout + sidebar
 -> ai-workspace.routes.ts
 -> ai-workspace.component.ts/html
 -> ai-workspace.facade.ts -> store + feature services
```

`demo.config.ts` chooses mock versus real providers. Route components compose UI only; HTTP, SSE and
DTO adaptation stay in services, while cross-component workflow state stays in the facade/store.

## Ask mode relationship

```text
chat-input.component output
 -> ai-workspace.component
 -> facade.ask(...)
 -> conversation.service.ts / ai-workspace.service.ts
 -> api/routes/ai_workspace_routes.py
 -> application/execution/execution_orchestrator.py
 -> application/chat/chat_service.py
 -> context/context_builder_service.py + repository services
 -> llm/application/llm_gateway.py
 -> Chat DTO mapper
 -> frontend store -> conversation/message-bubble/markdown-renderer
```

## Agent mode relationship

```text
chat-input Agent submission
 -> facade.runAgent(...)
 -> agent.service.ts
 -> ai_workspace_routes.py
 -> execution_orchestrator.py
 -> agent/agent_service.py
 -> tool_selection_service.py -> tool_execution_service.py -> tool_registry.py
 -> repository read/search/list/test/write/diff tools
 -> isolated_workspace_service.py + patch_validation_service.py
 -> execution/review stores + sse_event_publisher.py
 -> sse.service.ts/execution.service.ts
 -> store/selectors
 -> agent-plan + execution-timeline + file-change-card + review-panel
```

Review actions flow from `review-panel.component` through `review.service.ts` to `review_routes.py`,
`review_service.py`, and the review store. Apply continues through `workspace_transaction_service.py`,
which locks, verifies hashes, journals, writes atomically and supports rollback.

## Frontend module graph rules

```text
app route -> page container -> facade -> services/store
page container -> feature components
components -> input models + outputs + shared presentation utilities
services -> DTO models + HttpClient/SSE
mocks -> service contracts
components -X-> backend URLs or state stores directly
```

Models mirror backend DTO aliases: `execution.model.ts` ↔ `execution_dto.py`, `review.model.ts` ↔
`review_dto.py`, `workspace.model.ts` ↔ `workspace_dto.py`, and so on. Mappers belong at the backend DTO
boundary or frontend service boundary—not inside components.

## Repository dependency graph and AST status

Today, AI Workspace primarily discovers through `list_files_tool.py`, `search_repository_tool.py`,
`read_file_tool.py`, repository scan/search services and model reasoning. It does **not** yet maintain a
durable compiler-backed AST/symbol graph for TypeScript, Java or Python. This is a production-quality
gap for impact analysis, reference-safe edits and large-repository context selection.

The recommended architecture is:

```text
repository snapshot
 -> language adapters (TS compiler, Java parser/LSP, Python AST)
 -> normalized nodes: file, module, symbol, route, component, service, DTO, test
 -> typed edges: imports, exports, calls, injects, implements, routesTo, renders, tests
 -> graph index keyed by repository revision + file hash
 -> ContextBuilder queries relevant subgraph
 -> Agent receives evidence with source spans and confidence
 -> patch invalidates changed nodes and incrementally reparses dependants
```

Keep the graph behind an interface such as `CodeGraphProvider`; language-specific parsers are
infrastructure adapters. The application layer asks semantic questions and must not depend on parser
libraries. Dynamic/reflection edges are marked inferred or unresolved. Before changing a public symbol,
the Agent should query inbound references, affected routes, DTO consumers and tests, then include that
impact set in the plan and validation commands.

## Cross-layer modification rule

Adding a capability requires tracing component/output → facade/store → frontend service/model → route →
DTO mapper → application service → domain/state/tool → response/event → UI selector. Adding graph support
requires provider interface, language adapter, normalized graph schema, revision cache, context query,
incremental invalidation, telemetry and fixture-based accuracy tests.
