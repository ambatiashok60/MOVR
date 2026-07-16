# Component migration and integration playbook

## Portable frontend root

To embed API Test Generation, start at `frontend/test-generation/api-test-gen/api-test-gen.component.ts`.
Its portable closure is:

```text
api-test-gen.component.ts/html
 -> components/api-scenario-table/*
 -> components/mock-plan-review/*
 -> store/api-test-generation.facade.ts
 -> store/api-test-generation.store.ts + selectors.ts
 -> services/api-test-generation.service.ts
 -> services/api-test-generation-events.service.ts
 -> models/*.ts
 -> API prefix/provider tokens
 -> optional mocks/*
```

`test-generation.component.*` and `functional-test-gen/*` are host/composition examples; they are not required
when placing only API Tests inside an existing Worktop page. Integration examples under `integration/` show route
and host input wiring.

## Dependency manifest to inspect before copying

- Angular version and standalone-component support
- PrimeNG component/import names and version
- RxJS and TypeScript versions
- icon and stylesheet providers
- HttpClient/interceptors and API-envelope conventions
- route/lazy-loading convention
- authentication mechanism for REST and SSE
- story, repository and branch host models
- notification/dialog and permission services

If host versions differ, adapt the boundary imports/templates; do not fork business state across components.

## Backend closure for the real component

```text
frontend service URLs
 -> api_scenario_routes.py + api_test_generation_routes.py
 -> job_routes.py + event_routes.py
 -> request/result/job/event schemas
 -> generation_orchestrator.py
 -> discovery/profile/scenario/code/mock services
 -> strategies + tools + validators + workspace/task managers
 -> host tenant/DB/model/repository/task dependencies
```

## Exact migration procedure

1. Copy `models/`; compile and resolve naming differences.
2. Copy production services and define the API prefix injection token.
3. Copy store/selectors/facade; keep the facade as the component’s only workflow boundary.
4. Copy table and mock-plan components with their templates/styles/imports.
5. Copy the `api-test-gen` container and register its route or place its selector in the host template.
6. Connect inputs for selected story, repository, branch and tenant-safe context.
7. Connect outputs to host navigation, dialogs, notifications and code-review actions.
8. For preview, register `provide-api-test-generation-mocks.ts`; for production, remove that provider and set
   the real prefix. Do not modify component code.
9. Verify every frontend route against the backend contract and envelope.
10. Verify SSE auth/reconnect/terminal reconciliation, or use job polling until authenticated SSE is available.

## Dependency-closure test

After copying, search imports from the migrated root. Every relative import must resolve inside the copied slice;
every package import must exist in the host package manifest; every injected token must have exactly one provider;
and every HTTP path must map to a mounted backend route. A component that renders using fixtures but cannot
complete a real generate-scenario and generate-code workflow is not fully migrated.

## Acceptance walkthrough

Select a story → generate scenarios → receive job/events → render table → select scenario → open mock-plan review
when required → generate code → show changed files/validation/needs-review. Test success, backend validation error,
aborted job, disconnected SSE and mock-to-real provider switching.
