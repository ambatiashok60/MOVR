# Component migration and integration playbook

## Choose a portable boundary

The complete page root is `frontend/src/app/pages/ai-workspace/ai-workspace.component.ts`. Individual visual
components are reusable, but functional migration requires their state and service dependencies. Do not copy only
HTML and expect Ask, Agent, review or Apply behavior to follow.

## Full frontend dependency closure

```text
app.routes.ts / ai-workspace.routes.ts
 -> ai-workspace.component.ts/html
 -> components/*
 -> store/ai-workspace.facade.ts
 -> store/ai-workspace.store.ts + selectors.ts
 -> services/*
 -> models/*
 -> shared markdown/code/loading components and pipes/utilities
 -> app.config.ts providers + demo.config.ts switches
 -> Angular/PrimeNG/RxJS package and global style dependencies
```

For a smaller migration, calculate closure from the selected component:

| Component | Required functional boundary |
|---|---|
| conversation/message bubble | conversation models, markdown/code shared components; facade for live data |
| chat input/mode toggle | mode/prompt models and parent outputs; facade for submission |
| agent plan/timeline | execution models, selectors and SSE/execution services |
| file change/diff/review | file/review models, review service, facade/store and host authorization |
| workspace selector/context | workspace/context models and workspace/context services |

## Full backend closure

```text
frontend services
 -> app/api/routes/*
 -> DTOs + mappers
 -> execution orchestrator
 -> chat/agent/context/tool/review/session application services
 -> repository application services
 -> domain models
 -> state stores + SSE publisher + LLM adapters
 -> dependency container
 -> host auth/tenant/DB/model/repository/event configuration
```

Frontend model/backend DTO pairs are listed in document 07. Preserve those contracts or add one adapter; never
spread response-shape conversion across components.

## Migration procedure

1. Record the target host’s Angular, PrimeNG, routing, signals, styles, auth and API-envelope conventions.
2. Copy models and shared presentation dependencies first; compile.
3. Copy service interfaces/implementations and configure API/SSE base paths and interceptors.
4. Copy store/selectors/facade and verify providers have page-appropriate lifetime.
5. Copy selected leaf components, then the page container and route.
6. Add the host sidebar item to the lazy route; reuse the host layout rather than copying the demo shell.
7. Wire repository/branch/user context through an explicit host adapter.
8. Register mock providers only for preview. Switch to real providers without component edits.
9. Mount backend routers and replace placeholder dependencies with authenticated host providers.
10. Configure durable state, isolated workspaces, model client, task/event infrastructure and Apply authorization.
11. Run Ask, Agent, event, review, conflict and rollback integration tests.

## Import and provider audit

Build an import graph from the selected root. Classify every node as `copy`, `host-provided`, `replace-adapter`,
`package`, or `demo-only`. Classify DI providers similarly. The migration manifest should record source path,
target path, classification, API compatibility, replacement and verification test. This prevents forgotten pipes,
tokens, styles, interceptors and model mappings.

## Real-versus-mock acceptance gates

- The same component tree works with mock and real providers.
- Ask performs no mutation and renders evidence/error states.
- Agent receives an execution ID, updates plan/timeline, stages changes and survives SSE reconnect.
- Review decisions bind to patch revisions and dependent rejections are reconciled.
- Apply uses host authorization and hash-conflict handling.
- Tenant, repository and branch come from trusted host context.
- Browser refresh/resume reconstructs durable execution state.
- No `demo.config.ts` mock provider is enabled in production.

## Example: place review panel in another page

Copying `review-panel.component.*` alone provides presentation only. Functional placement also requires
`file-change-card`, `diff-viewer`, review/file-change models, review service, relevant facade/store slice and host
authorization outputs. If the new page already owns state, implement an adapter that supplies the component inputs
and handles outputs instead of creating a second AI Workspace store. Verify keep/reject/revise, stale patch,
dependent-file rejection and Apply-disabled states before considering the migration complete.
