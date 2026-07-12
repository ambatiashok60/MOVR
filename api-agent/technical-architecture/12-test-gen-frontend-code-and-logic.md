# Test Gen frontend code and logic

## Component boundary

`frontend/test-generation/test-generation.component.ts` is the portable Test Gen shell. It owns only the
Functional/API tab selection and passes host context to the API child. It does not own repository selection,
story retrieval, authentication, API calls, scenario state or code-generation state.

```text
TestGenerationComponent
 ├─ FunctionalTestGenComponent       presentation placeholder/reference
 └─ ApiTestGenComponent              functional API-generation feature
     ├─ ApiScenarioTableComponent
     ├─ MockPlanReviewComponent
     ├─ ApiTestGenerationFacade
     ├─ ApiTestGenerationStore/selectors
     └─ REST and SSE services
```

## Inputs and ownership

| Input/state | Owner | Consumer | Rule |
|---|---|---|---|
| `selectedStory` | host story page | API child/facade | null disables story-dependent generation |
| `tenantId` | authenticated host context | API requests | production must not trust it for authorization |
| `repoPath` | host repository registry | API requests | backend resolves/authorizes real workspace |
| `branch` | host repository selector | API requests/display | refresh evidence when branch/revision changes |
| `activeTab` | Test Gen shell | shell template | local view state; no backend persistence required |
| scenario/job/review state | API facade/store | API components | never duplicate in shell or host page |

`setTab()` changes view composition only. Because the template uses `*ngIf`, switching tabs destroys and
recreates the child. If workflow state must survive tab switches, provide the store above the conditional view
or replace destruction with a keep-alive design. Document this choice when integrating.

## Template logic

`test-generation.component.html` renders the page title and tab strip. The Functional child is rendered only
for `activeTab === 'functional'`. The API child receives all four context inputs. The shell must not invoke API
services directly; its role is composition and context propagation.

## API child logical flow

```text
input change/initialization
 -> facade receives story/repository context
 -> store records selection and resets stale scenario state when identity changes
 -> Generate Scenarios action
 -> facade validates prerequisites
 -> REST service starts task
 -> SSE service observes progress; job polling reconciles/recoveries
 -> store reduces events and terminal result
 -> selectors project table/loading/error/review state
 -> table emits scenario selection/action
 -> facade starts Generate Code
 -> MockStubPlan/review result appears when required
```

Components emit user intent. The facade decides workflow order. The store owns state transitions. Services own
transport. Selectors translate domain state into display state. This separation must remain after migration.

## Suggested shell state machine

```text
functional tab <-> api tab

API child:
idle -> missing_context | ready
ready -> generating_scenarios -> scenarios_ready | error
scenarios_ready -> generating_code -> validating
validating -> completed | needs_review | error | aborted
```

Changing story/repository/branch while a task is active should request confirmation or abort/detach the prior
task, then create a new context revision. Late SSE events must be ignored when their task/context ID is stale.

## Routing alternatives

Use `TestGenerationComponent` when Functional and API tabs share one page. Use
`API_TEST_GENERATION_ROUTES` when the host already owns Test Gen tabs and needs only the API child. Do not mount
both as competing state owners. The host route should be lazy and the sidebar should navigate to it; the feature
component must not create its own global layout/sidebar.

## Complete migration manifest

Copy for the full Test Gen shell:

- `test-generation.component.ts/html/scss`
- `functional-test-gen/*` if the target lacks its existing Functional implementation
- the complete `api-test-gen` dependency closure listed in document 11
- `api-test-generation.routes.ts` only when route-based child integration is chosen

Replace rather than copy:

- host story table and selection service
- repository/branch selectors
- authenticated tenant context
- navigation, permission, notification and dialog services
- existing Functional Test Gen component, when Worktop already owns it

## Functional integration example

```html
<app-test-generation
  [selectedStory]="selectedStory()"
  [tenantId]="tenantContext.tenantId()"
  [repoPath]="repositoryContext.path()"
  [branch]="repositoryContext.branch()"
/>
```

In production, prefer a tenant-safe host context object or backend session over manually entered identity. If
the existing Functional component uses different story/repository models, add a shell adapter that maps both
children from one canonical host context instead of letting each child interpret host models independently.

## Verification matrix

| Test | Expected proof |
|---|---|
| shell render | both tabs visible; correct default tab |
| tab switching | correct child rendered; state-survival behavior matches chosen policy |
| null story | API actions disabled with readable guidance |
| context change | stale results cleared/detached; late events ignored |
| mock mode | full table/code/review UX without backend |
| real mode | same component tree calls mounted routes |
| REST failure | facade/store exposes recoverable error |
| SSE disconnect | reconnect/poll reconciliation preserves one terminal state |
| authorization failure | no generation; host-standard permission message |
| responsive/accessibility | keyboard tabs, focus, labels and drawer behavior work |

## Known current gaps

The portable shell has simple local tab state and its Functional child is a reference rather than the actual
Worktop Functional Test Gen implementation. It does not yet expose tab-change outputs, URL-synchronized tabs,
unsaved-task navigation guards or a canonical combined context model. Those should be implemented in the host
adapter if required, without moving API workflow logic into the shell.
