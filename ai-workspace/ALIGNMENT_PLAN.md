# AI Workspace Alignment With Test Agent And API Agent

## Implemented now

- Worktop `DefaultLLMClient` remains the preferred tenant-aware model integration.
- Selected repository context is protected by restricted-file blocking and secret redaction.
- Agent-plan JSON can be extracted from prose/fences and receives one repair call when invalid.
- LLM calls, prompt/completion characters, and elapsed time are review estimates, not blockers.
- Estimate overages set `needsReview` and `reviewReasons`; actual usage is returned as `budgetUsage`.
- Model changes remain staged until explicit file-level review and Apply.
- Existing path safety, command allowlist, persistent stores, and SSE infrastructure remain.
- Regression tests cover governance, structured parsing, and review-first estimates.

## Milestone 1 — Iterative coding-agent loop (implemented)

Agent Mode now uses a bounded loop:

```text
plan -> choose tool -> execute -> observe -> revise -> propose patch -> validate -> repair
```

Implemented: structured turns and observations, autonomous read/search/list tools, evidence and
root-cause gates, turn/repetition limits, data-governed observations, staged patches, deterministic
Python/JSON/path validation, one bounded repair turn, detailed events/logs, and an evidence-based
engineering review. Apply is not model-callable.

Repository-native builds/tests against an isolated worktree, cancellation checks, and multi-round
compiler-driven repair belong to the workspace-hardening milestone below.

## Phase 3 — Asynchronous execution and SSE

`POST /agent/run` currently awaits completion. Change it to enqueue and immediately return an
execution ID, persist state before work starts, replay buffered events for late subscribers, wire
the Angular facade to SSE, and implement cancellation/retry. Multi-instance deployments require
Redis/Valkey pub/sub.

## Phase 4 — Workspace and review hardening

Core Milestone 2 protections are implemented: detached worktree/copy isolation, proposal-time
fingerprints, repository locks, snapshots, stale-proposal rejection, apply journals, transactional
rollback, and correct delete semantics. Remaining work is repository-native validation inside the
isolated workspace and cleanup/retention policy for completed worktrees.

- Lock the repository during Apply.
- Snapshot targets and journal apply/rollback operations.
- Detect files changed since the proposal was generated.
- Add risk approval for command execution and sensitive tools.
- Attach governance and validation evidence to the review surface.

## Phase 5 — Production verification

- Add `pytest-asyncio` and async route/orchestrator tests.
- Cover traversal, cross-tenant access, review/apply, SSE, cancellation, restart, and shared state.
- Verify real Worktop DB/tenant dependencies and authenticated SSE.
- Add tracing and monetary/token metrics when real model responses expose usage.
