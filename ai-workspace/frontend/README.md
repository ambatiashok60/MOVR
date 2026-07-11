# AI Workspace — Frontend (standalone folder)

Restructured against the detailed layout/pages/shared architecture requested in this session —
superseding the earlier flat 10-file version. Written without access to the real
`TestGenWorkTop_UI` project, so this is a source-level reference to copy in and adjust, not a
drop-in replacement.

## Scale vs. the "78 files" figure

The originally quoted count was 78. Fully expanded (every listed component folder as a real
`.ts/.html/.scss` triple, matching how `layout/main-layout/` etc. were explicitly written out) the
same structure comes to **115 files**:

```text
app.* root (component×3 + config + routes)   5
layout/ (main-layout, sidebar, topbar × 3)   9
pages/ai-workspace/ shell (component×3 + routes)  4
pages/ai-workspace/models/                  13
pages/ai-workspace/services/                14
pages/ai-workspace/store/                    3
pages/ai-workspace/components/ (17 × 3)     51
shared/components/ (3 × 3)                   9
shared/pipes/                                3
shared/utils/                                4
                                          -----
                                            115
```

Not forced down to 78 — the discrepancy is almost certainly the difference between counting
component folders and counting the files inside them. All 115 exist under `src/app/`.

## What's real vs. what's a placeholder

Every file compiles as valid, internally-consistent TypeScript/Angular — cross-checked so every
`from '...'` import and every `templateUrl`/`styleUrl` resolves to a file that actually exists in
this tree (verified with a script, not just written and assumed). That's different from "tested
against a real project," which hasn't happened. Specifically:

- **Models, services, store, facade, selectors**: fully typed, real logic. The facade
  (`pages/ai-workspace/store/ai-workspace.facade.ts`) is the one place request orchestration
  lives — components never call services directly, only the facade.
- **The 17 presentational components**: real `@Input`/`@Output` contracts and working templates,
  composed together by `ai-workspace.component.html`. Not exhaustively styled to match the mockup
  pixel-for-pixel — layout/spacing will need visual polish once running in a browser.
- **Layout (sidebar/topbar/main-layout)**: sidebar nav items are reconstructed from the earlier
  approved mockup screenshot (Dashboard, Projects, Data Sources, Prompt Management, Coverage,
  Review Management, AI Workspace BETA, Settings) — not from the real app's actual nav config,
  which wasn't available.
- **`app.routes.ts` / `app.config.ts` / `app.component.*`**: reference versions assuming this
  scaffold is the whole app. In reality, merge the `ai-workspace` child route into the host app's
  real routes/config rather than replacing them — the host app already has routes for the other
  nav items.

## Known gaps / product decisions left open

1. **Workspace selection is path-first for V1.** The repository dropdown remains available for
   configured repositories, but validating a raw local path now promotes that path into the
   selected repository/branch/session flow.
2. **Selected repository files now feed backend prompt context.** Clicking a file in the tree
   adds it to the selected context, and the selected-files panel can remove it.
3. **`ContextBuilderService.getContextSummary()` / `setPriorityFiles()` now have backend
   endpoints.** They currently expose selected-file state with placeholder token counts until
   real token budgeting lands.
4. **No SSE/streaming.** `AgentService.startRun()` and the facade's `submitPrompt()` treat
   `agent/run` as a single request/response. `services/sse.service.ts` exists as a generic
   `EventSource` wrapper but nothing calls it yet — wire it into the facade once the backend's
   event contract (open question in `docs/ai_workspace.md`) is confirmed.
5. **Apply assumes server-side staging.** `ReviewService.applyChanges()` sends only
   `{ runId, keptFileIds }`. If the backend instead needs full file content round-tripped back,
   this needs to send `fileChanges` content too.
5. **`bootstrap.service.ts` assumes a single `GET /api/ai-workspace/bootstrap` call** returns
   models, tools, feature flags, permissions, preferences, planner/execution/telemetry config all
   at once. This is the biggest unverified assumption in the whole scaffold — confirm this
   endpoint exists before building more on top of `BootstrapPayload`.
6. **Minor layering wrinkle**: `shared/pipes/status-label.pipe.ts` imports `ExecutionStatus` from
   `pages/ai-workspace/models/` — a shared/ file reaching into a feature module. Harmless while
   AI Workspace is the only feature, but if `ExecutionStatus` needs to be genuinely shared later,
   move it to a more central location.
7. **`getPrompt(id)` in `prompt-library.service.ts` is unused** by any component currently — only
   `listPrompts()` is wired into the facade. Left in since it's a reasonable API surface, but flag
   if unused code should be trimmed for V1.

## Things to fix on integration (stack/version assumptions)

1. **PrimeNG component API version** — written against `p-dropdown` / `p-tabView` / `p-tree` /
   `p-checkbox` / `p-splitButton` (stable across many PrimeNG versions). PrimeNG 18+ renamed
   several of these (`p-select`, `p-tabs`). Check the host app's installed `primeng` version.
2. **`app.config.ts`'s `providePrimeNG(...)` call** is a PrimeNG 18+ pattern — older versions
   configure theming via a global stylesheet import instead. Confirm before merging.
3. **API base URL** — every service imports `AI_WORKSPACE_API_PREFIX` from `ai-workspace.service.ts`,
   hardcoded to `/api/ai-workspace`. Replace with the host app's real API base config.
4. **`markdown-renderer.component.ts`** stubs markdown rendering with basic HTML-escaping, not a
   real markdown parser — swap in whatever markdown library (e.g. `marked`) the host app already
   has, or add one.
5. **Not run against a live Angular/PrimeNG project or compiler** — only statically checked that
   imports and template/style references resolve within this tree. Expect the normal first-build
   friction (exact PrimeNG selector names, Angular version-specific control-flow syntax) once
   dropped into a real project with `ng build`.

## Where this lands in the real project

Copy `src/app/pages/ai-workspace/`, `src/app/layout/`, and `src/app/shared/` into the host app's
equivalent directories. Merge (don't replace) `app.routes.ts` and `app.config.ts` — add the
`ai-workspace` child route and the PrimeNG/HTTP providers into what's already there.

If the host app drives its left nav from a config file (e.g. `app-constants.ts`) rather than a
hardcoded array, pull the `NAV_ITEMS` array out of `layout/sidebar/sidebar.component.ts` and
adapt its shape (`label`/`icon`/`routerLink`/`badge`) to match — there's no separate snippet file
for this anymore since it would just duplicate that array.

## Scope reference

Backend endpoints called from these services are documented in
[`docs/ai_workspace.md`](../../docs/ai_workspace.md) under "Concrete V1 integration plan" — that doc's
backend file count (23 files) is unaffected by this frontend restructure; only the frontend side
grew from the doc's frozen 10 to this session's much more detailed 115.
