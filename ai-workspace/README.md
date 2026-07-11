# AI Workspace

## Executive Summary

`ai-workspace` is the consolidated module for the Copilot-style workspace
experience. It contains both the FastAPI backend scaffold and the Angular
frontend scaffold under one feature folder, following the same top-level
kebab-case naming convention as `test-agent`.

The module is intentionally split by runtime:

```text
ai-workspace/
├── backend/   FastAPI service scaffold
└── frontend/  Angular + PrimeNG UI scaffold
```

This replaces the earlier root-level folders:

```text
AI_Workspace_backend
AI_Workspace_frontend
```

## Functional Goal

AI Workspace gives a developer a repository-aware Chat Mode and Agent Mode
inside the platform. The user selects or validates a local workspace, builds
context from repository files, asks questions, runs agent tasks, reviews
proposed changes, and explicitly applies the kept changes.

The core product flow is:

```text
Open AI Workspace
        |
Select or validate a repository workspace
        |
Create or resume a session
        |
Choose Chat Mode or Agent Mode
        |
Build repository and conversation context
        |
Call the existing model integration
        |
Show response, plan, timeline, and changed files
        |
Keep or reject proposed file changes
        |
Apply only the kept changes
```

## What Was Consolidated

The current scaffold includes:

- `backend/`: FastAPI routes, domain models, application services,
  repository access, LLM adapter boundaries, execution orchestration, review
  services, tool registry, and durable SQLite-backed state stores.
- `frontend/`: Angular shell, AI Workspace page, feature components, typed
  models, services, facade/store layer, shared display utilities, and layout
  scaffolding.
- Module-level documentation that explains how both halves fit together.

Detailed implementation notes remain in:

- [`backend/README.md`](backend/README.md)
- [`frontend/README.md`](frontend/README.md)
- [`../docs/ai_workspace.md`](../docs/ai_workspace.md)

## Scope - In For V1

```text
AI Workspace V1
├── Chat Mode / Ask Mode
├── Agent Mode
├── Local workspace path validation
├── Repository scan for context
├── Priority file selection
├── Model registry from backend
├── Tool registry from backend
├── Prompt/context builder
├── LLM integration using the existing model client through an adapter/factory
├── File read/write tools
├── Git diff tool
├── Test command tool
├── Execution planning
├── SSE timeline infrastructure
├── Review changed files
├── Keep/reject/apply changes
└── Session history
```

## Scope - Explicitly Out For V1

```text
Not part of AI Workspace V1
├── Story Intelligence
├── Jira analysis
├── Ambiguity scoring
├── Coverage Intelligence
├── Suite Optimizer
├── Code Health Intelligence
├── Stage regression intelligence
├── Dedicated Worktop test intelligence modules
├── Distributed queues/background workers
├── MCP server integration
├── Advanced retrieval infrastructure
└── Multi-instance distributed execution stores
```

These may later be exposed through AI Workspace as tools or adjacent modules,
but they should not be folded directly into the AI Workspace V1 scope.

## Backend Scope

The backend lives at:

```text
ai-workspace/backend
```

It owns the API and service boundary for sessions, workspace validation,
repository context, Chat Mode, Agent Mode, execution events, file review, and
apply flows.

The backend scaffold is standalone for development, but it is expected to be
merged into the existing platform backend rather than run as a second long-term
FastAPI app. It should reuse the platform's existing auth, tenant, database,
and model-client wiring.

## Frontend Scope

The frontend lives at:

```text
ai-workspace/frontend
```

It owns the Angular source-level scaffold for the AI Workspace screen,
including the layout, chat thread, workspace selectors, context panels,
execution timeline, diff/review surfaces, settings, models, services, and
facade/store orchestration.

The frontend scaffold is a reference implementation to merge into the host
Angular app. The host app's real routing, navigation configuration, PrimeNG
version, theme setup, and API base configuration still need to be reconciled
during integration.

## Supported Repository Scope

V1 is designed for local repositories that can be inspected from disk and where
basic source, test, package, and Git signals are available without remote
infrastructure.

Good V1 targets include:

- Single frontend app repositories.
- Simple monorepos with obvious ownership boundaries.
- TypeScript/Angular or TypeScript/React projects.
- Repositories with local test commands and predictable package scripts.
- Repositories where file reads, file writes, and Git diffs are safe to perform
  after explicit user review.

Repositories that need additional adapters include:

- Complex monorepos with ambiguous app/test ownership.
- Repositories requiring secrets, containers, or remote services for basic
  validation.
- Highly custom internal test DSLs.
- Workflows where generated changes must go through a separate approval system
  before touching the working tree.

## Naming Convention

Top-level feature folders should use kebab-case:

```text
test-agent
ai-workspace
```

Runtime-specific implementation folders inside a feature should use plain,
lowercase names:

```text
backend
frontend
```

Python package names inside the backend can keep snake_case where Python import
conventions require it, such as `app/ai_workspace`.

## Current Integration Status

The scaffold is ready for source review and integration planning, but not yet a
drop-in production module. The frontend/backend contract has been aligned around
`/api/ai-workspace/...` endpoints, camelCase JSON payloads, and a path-first
workspace flow that can promote a validated local path into the selected
repository/session.

The important remaining integration points are:

- Follow the detailed backend convergence plan in [`ALIGNMENT_PLAN.md`](ALIGNMENT_PLAN.md).

- Confirm the real existing model-client import path and method contract in the host environment.
- Replace local fallback database and tenancy dependencies with platform-owned
  dependencies.
- Wire SSE events into the frontend facade once the event contract is final.
- Use `AI_WORKSPACE_STATE_BACKEND=mysql` for shared MySQL-backed state when multiple
  backend instances need to see the same AI Workspace sessions/reviews.
- Run the frontend against the host Angular/PrimeNG project and resolve version
  differences.
