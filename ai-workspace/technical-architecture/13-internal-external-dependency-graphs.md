# Internal and external dependency graphs

## Frontend application graph

```text
main.ts -> app.config.ts -> app.routes.ts
 -> layout/main-layout/* -> layout/sidebar/* + layout/topbar/*
 -> pages/ai-workspace/ai-workspace.routes.ts
 -> pages/ai-workspace/ai-workspace.component.ts/html

ai-workspace.component.ts
 -> store/ai-workspace.facade.ts
 -> components/workspace-header, mode-toggle, conversation, chat-input
 -> components/context-panel, selected-files-panel
 -> components/agent-plan, execution-timeline
 -> components/file-change-card, diff-viewer, review-panel
 -> components/settings, sessions, prompt-library
```

## Frontend state and transport graph

```text
ai-workspace.facade.ts
 -> ai-workspace.store.ts + selectors.ts
 -> bootstrap.service.ts
 -> workspace.service.ts + context-builder.service.ts
 -> session.service.ts + conversation.service.ts
 -> ai-workspace.service.ts + agent.service.ts
 -> execution.service.ts + sse.service.ts
 -> review.service.ts
 -> model-registry.service.ts + tool-registry.service.ts
 -> models/*.ts
```

Components receive state and emit intent; they do not call URLs. Services depend on HttpClient/SSE and models.
Mock providers replace services at DI boundaries. Shared markdown/code/loading components remain presentation-only.

## Backend control and application graph

```text
backend/app/main.py
 -> api/routes/ai_workspace_routes.py
 -> session_routes.py + workspace_routes.py
 -> execution_routes.py + sse_routes.py
 -> review_routes.py + model_routes.py + tool_routes.py
 -> dependencies/container.py + specialized dependency modules

ai_workspace_routes.py
 -> execution/execution_orchestrator.py
 -> chat/chat_service.py OR agent/agent_service.py

agent_service.py
 -> context/context_builder_service.py
 -> context/repository_memory_service.py
 -> prompts/prompt_builder_service.py
 -> tools/tool_selection_service.py
 -> tools/tool_execution_service.py
 -> tools/tool_registry.py
 -> agent/patch_validation_service.py
 -> review/diff_service.py + engineering_review_service.py
```

## Repository, mutation and state graph

```text
tool implementations
 -> repository/application/file_read_service.py
 -> repository_search_service.py + repository_scan_service.py
 -> repository_tree_service.py
 -> git_diff_service.py
 -> file_write_service.py
 -> isolated_workspace_service.py
 -> workspace_transaction_service.py

repository application interfaces
 -> infrastructure/local_repository_access_provider.py
 -> infrastructure/local_file_writer.py
 -> infrastructure/git_cli_provider.py

application services
 -> domain/*.py
 -> infrastructure/state_store.py
 -> in_memory_* OR sqlite_state_store.py OR mysql_state_store.py
 -> sse_event_publisher.py
```

## LLM graph

```text
chat/agent application service
 -> llm/application/llm_application_service.py
 -> llm_gateway.py + llm_stream_service.py
 -> llm_client_factory.py
 -> infrastructure/default_llm_client_adapter.py
 -> infrastructure/model_client_streaming_adapter.py
 -> Worktop model client

explicit preview only:
llm_client_factory.py -> infrastructure/mock_llm_client.py
```

The application layer depends on LLM/tool/repository interfaces. Infrastructure adapters depend inward on those
contracts. Domain objects have no FastAPI, Angular, database, filesystem, Git, subprocess or model-client imports.

## Combined Test Gen dependency

The preview imports `api-agent/frontend/test-generation` through the `@api-test-generation/*` TypeScript alias.
This is a source-level development dependency, not a production package boundary. Production should copy/package
the feature or map it into the Worktop monorepo build deliberately. AI Workspace components do not depend on Test
Gen components; both are siblings under the shared host layout.

## External dependency graph

| External system/library | Internal consumers | Required adapter/control |
|---|---|---|
| Angular/PrimeNG/RxJS | frontend | host routing, DI, version and theme alignment |
| Browser EventSource | SSE service | fetch-SSE replacement for bearer authentication |
| FastAPI/Pydantic/settings | routes/DTO/config | router and platform-envelope integration |
| Worktop authentication/tenant/DB | dependency container | trusted providers; no request tenancy |
| Worktop model gateway | LLM infrastructure | adapter, timeout, usage and cancellation |
| Local/Git repository | repository infrastructure | containment, authorization, leases and hashes |
| Filesystem/subprocess/test tools | Agent tools | sandbox, allowlist, timeout and cancellation |
| SQLite/MySQL | state stores | transaction/migration/retention policy |
| Redis/Valkey or platform queue | future tasks/events | dispatcher, durable event/replay interfaces |
| GitHub/CI/devcontainer | remote preview/validation | Node 20 and secret-safe workflows |
| API Agent portable frontend | combined preview | package/source alias and contract versioning |

## Forbidden dependency directions

- Domain must not import routes, stores, infrastructure or framework code.
- Application services must not instantiate concrete DB, filesystem, Git, queue or model clients.
- Routes must not implement Agent decisions or repository mutations.
- Frontend components must not call HttpClient/EventSource or mutate stores directly across feature boundaries.
- State/event infrastructure must not decide execution completion independently of the orchestrator/task owner.
- Memory must not override current repository evidence or grant tool authority.
- AI Workspace and Test Gen may share host services but must not import each other’s feature state.

## Graph maintenance

Generate a machine-readable import graph in CI and compare it with allowed layer rules. Runtime edges that imports
cannot show—DI providers, routes, event publishers, queue handlers, model adapters and configuration-selected
stores—must be recorded as explicit architecture metadata. Any public file move should update this document,
component migration manifests and contract tests in the same change.
