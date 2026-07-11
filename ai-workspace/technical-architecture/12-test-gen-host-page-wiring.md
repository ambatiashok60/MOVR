# Combined preview Test Gen host wiring

## Role of the preview page

`frontend/src/app/pages/test-generation/test-generation-page.component.ts` is a design-review host scaffold.
It demonstrates how Worktop supplies repository, branch and story context to the portable Test Gen component
imported from `api-agent/frontend/test-generation`. It is not the production story/repository implementation.

```text
app.routes.ts
 -> MainLayoutComponent
 -> /test-generation lazy TestGenerationPageComponent
 -> host header + story table
 -> imported TestGenerationComponent
 -> FunctionalTestGenComponent / ApiTestGenComponent
```

## File relationships

- `app.routes.ts`: mounts `/test-generation` under the shared layout.
- `layout/sidebar/*`: navigates to the route; it must not own feature state.
- `test-generation-page.component.ts`: owns preview signals for repository, branch, stories and selection.
- `test-generation-page.component.html`: renders host context/story UI and binds the selected context.
- `@api-test-generation/*`: TypeScript alias to the portable API Agent frontend source.
- `app.config.ts` and `demo.config.ts`: register HTTP and mock/real providers.

The page currently imports `MOCK_STORY`; production must replace that with the Worktop story/JIRA store. The
hard-coded tenant, repository path and branch become authenticated host context. The template’s story actions are
visual scaffolding until connected to real analyze/design/flow services.

## Production replacement map

| Preview item | Production replacement |
|---|---|
| `signal('wfm-repo')` | repository selector/store |
| `signal('feature/...')` | branch selector/store |
| `signal('/repos/...')` | backend-authorized repository ID/path adapter |
| `MOCK_STORY` | JIRA/story query and normalized story adapter |
| `tenantId=1` | authenticated tenant context |
| simple row toggle | host selection policy/store |
| visual action buttons | existing story-analysis facade/actions |
| mock providers | real API/SSE providers |

## Context-change logic

Repository change invalidates branch, story-derived repository evidence and scenario results. Branch change
invalidates repository profile/scenario freshness. Story change invalidates selected scenarios and generated-code
context but need not discard cached repository discovery when its revision remains identical. These invalidations
belong in the host adapter/facade, not in the story table template.

## Migration into Worktop

1. Add the lazy route to the existing host child routes; do not replace `app.routes.ts`.
2. Add the sidebar entry using the host navigation model and permission guard.
3. Replace preview signals and fixtures with selectors from host stores.
4. Map the Worktop story model to `SprintApiStory` in one adapter.
5. Bind the portable Test Gen shell, or bind `ApiTestGenComponent` directly if Worktop owns the tabs.
6. Register real API/SSE providers and host envelope/auth adapters.
7. Reuse the production Functional Tests component rather than the preview placeholder.
8. Add context-change guards for active tasks and stale events.

## End-to-end acceptance

Navigation opens the page inside the existing layout; repository/branch/story selection comes from real host
state; Functional Tests preserve existing behavior; API Tests generate scenarios and code; mock-plan review and
terminal errors render; refresh/resume reconciles tasks; changing context cannot display stale results; and no
preview fixture, hard-coded tenant or demo provider remains in the production bundle.

For the complete portable shell dependency closure and state logic, see the API Agent document
`technical-architecture/12-test-gen-frontend-code-and-logic.md`.
