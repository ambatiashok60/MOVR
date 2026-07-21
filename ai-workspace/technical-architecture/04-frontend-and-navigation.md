# Frontend composition and navigation wiring

`app.routes.ts` lazily exposes AI Workspace and the combined Test Generation preview. `layout/sidebar/`
is the host-shell reference. `pages/ai-workspace/` composes conversation, explorer, plan, timeline and
review drawer. `store/ai-workspace.store.ts` owns state; the facade orchestrates services and UI actions.
Components remain presentational and services own REST, SSE, sessions, workspace, review, models and tools.

Worktop should add a side-navigation item pointing to the lazy route and preserve a single page shell:
conversation and composer remain primary, while context and execution details use collapsible panels;
file diff and decisions use a review drawer. Ask hides mutation controls. Agent exposes the plan,
timeline, staged files and Apply only when authorization and review state allow it.

Use one adapter for host envelopes, notifications and authentication. Do not duplicate host navigation
or add mock branches inside components.
