# Repository exploration and planner UX

This integration applies RepoAgent's clearest interaction patterns to Agentic
Workspace Chat without introducing a second agent runtime.

## Product expectation

The page answers five questions at a glance:

1. **What repository is connected?** The left tree supports search, folder
   expansion, and explicit context selection.
2. **What is happening now?** A four-stage lifecycle shows Understand, Explore,
   Plan, and Complete while the bounded request runs.
3. **What is the agent's plan?** The right panel shows an immediate three-step
   working plan, then replaces it with the model's published plan.
4. **What evidence did it use?** Relevant files combine explicit selections,
   relationship evidence, and proposed file changes.
5. **What can change?** Proposed edits and generated actions remain in the
   explicit review/apply boundary; nothing writes automatically.

## Page flow

```text
Connect path
  → validate allowed root
  → scan bounded text files once
  → return tree + repository summary
  → select optional context
  → send Ask/Debug/Analyze/Migrate/Refactor/Test request
  → show lifecycle + working plan
  → run bounded Bedrock/tool loop
  → show answer + real plan + evidence + activity
  → review and explicitly apply accepted changes
```

## Three-pane information architecture

- **Left — Explore:** repository identity, searchable file tree, selected context.
- **Center — Work:** lifecycle, evidence-backed conversation, stop/retry, prompt.
- **Right — Understand and review:** repository overview, plan, relevant files,
  counters, validation, latest actions, and change review only when needed.

The right panel intentionally uses compact sections rather than multiple modes
or nested navigation. Repository exploration remains the primary workflow.

## Runtime boundary

This is a presentation and exploration integration, not a merger of RepoAgent's
SSE run engine with Agentic Workspace Chat. The existing bounded HTTP request,
disconnect cancellation, Bedrock timeouts, proposal isolation, and explicit
apply model remain authoritative. A future move to live planner updates should
adopt a run-ID/SSE contract as a separate architecture decision.
