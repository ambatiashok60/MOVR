# API Test Generation Frontend Scaffold

Portable Angular source for adding an **API Tests** table beside an existing Functional Tests
experience. The real Worktop frontend is not in this checkout, so this is an integration package,
not a replacement Angular application.

## Architecture

```text
api-test-gen/                         thin feature container
components/api-scenario-table/       presentation-only table
models/                              backend and table contracts + adapter
services/                             REST and SSE clients
store/                                signal state, selectors and orchestration facade
api-test-generation.routes.ts        optional lazy feature route
integration/                          commented host-app merge examples
```

The table receives rows through inputs and emits user actions. It never injects an API service.
The container calls `ApiTestGenerationFacade`; the facade is the only request-orchestration layer.

## Preferred embedded-tab integration

Keep the existing Functional Tests component unchanged. Import `ApiTestGenComponent` in the host
Test Generation page and render it only for the API tab:

```html
<app-api-test-gen
  *ngIf="activeTab === 'api'"
  [selectedStory]="selectedStory"
  [tenantId]="tenantId"
  [repoPath]="selectedRepository.path"
  [branch]="selectedBranch.name"
/>
```

See `integration/host-test-generation.example.*` for commented wiring. If API Tests needs its own
URL, merge the route from `integration/host-app.routes.example.ts` into the host routes. Never
replace the host `app.routes.ts` or `app.config.ts` with these reference files.

## Host responsibilities

1. Own Functional/API tab state, selected story, repository and branch selection.
2. Keep the existing `provideHttpClient(...)`, auth interceptors and notifications.
3. Configure `API_TEST_GENERATION_PREFIX` if `/api/api-test-generation` is not correct.
4. Decide whether edit/delete actions open existing dialogs; their container hooks are no-ops.
5. Enrich table dependencies if the host/backend has structured dependency data.

## SSE authentication

`ApiTestGenerationEventsService` uses native `EventSource` with cookies. Angular interceptors do
not add bearer headers to `EventSource`. A bearer-only host must replace that service with its
authenticated fetch-based SSE utility or use a backend-issued stream token.

## Backend flow

```text
Generate API Scenarios -> queued task -> SSE terminal event -> GET job -> table rows
Generate code on row   -> queued task -> SSE terminal event -> GET job -> generated result
```

The display adapter deliberately separates `ApiScenario` from `ApiScenarioTableRow`, keeping the
visual component stable when backend response details evolve.

## Budget estimates

Budget thresholds default to review mode. Exceeding estimated LLM calls, tool calls, repository
reads, prompt size, or elapsed time does not stop generation; the result is marked for review and
the frontend displays actual usage and threshold findings. Set `BUDGET_ENFORCEMENT_MODE=strict`
only when the host needs hard ceilings.
