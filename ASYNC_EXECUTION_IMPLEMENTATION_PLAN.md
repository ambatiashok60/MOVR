# Shared asynchronous execution implementation plan

This plan applies to Test Agent, API Agent and AI Workspace. The feature orchestrators remain independent;
task lifecycle, cancellation, concurrency, events and frontend reconciliation use one shared foundation.

## Phase 1 — Shared contracts and state model

Define versioned task, event, error, cancellation and result contracts. Normalize legal states and transitions:
`queued`, `starting`, `running`, `cancellation_requested`, `cancelled`, `needs_review`, `completed`, `failed`,
with optional `retry_scheduled`, `timed_out` and `orphaned`. Define idempotency, ownership and terminal-write rules.

## Phase 2 — Task and event abstractions

Introduce `TaskRepository`, `EventRepository`, `TaskDispatcher`, `CancellationToken` and feature-handler
interfaces. Orchestrators receive a runtime context and never depend directly on a thread pool or queue vendor.

## Phase 3 — Local bounded workers

Implement single-process development execution with a bounded executor. Persist the task before enqueueing,
return HTTP 202 immediately, create DB/model/workspace dependencies inside the worker, and keep locks short.

## Phase 4 — Resource concurrency and semaphores

Add independent limits for global tasks, per tenant, per repository mutation, LLM calls, command/browser/container
execution and SSE clients. Use distributed repository leases when multiple processes can execute work.

## Phase 5 — Cooperative cancellation

Implement cancellation requests, tokens and checkpoints between stages and model/tool/file operations. Replace
uncancellable subprocess calls with controllable processes and process-group cleanup. Publish requested and final
cancelled states; preserve cleanup and rollback evidence.

## Phase 6 — Durable production workers

Adopt the existing Worktop queue when available, otherwise choose one supported queue implementation. Add task
claims, leases, heartbeats, retries, dead-letter handling, worker-loss recovery, graceful shutdown and durable
state/events. Do not couple domain orchestration to the selected queue library.

## Phase 7 — SSE replay and polling reconciliation

Give events monotonic IDs/sequences, durable buffering and resume-from-last-event support. The frontend opens SSE
and also performs slower authoritative job polling. On disconnect it polls faster and reconnects with jitter.
Completed, failed and cancelled states close streams and trigger one final result fetch.

## Phase 8 — Shared frontend Run/Abort lifecycle

Create a reusable frontend task controller/facade for run, cancel, event connection, polling, reconciliation and
cleanup. Align button states and ignore late events from stale task/context revisions. Mocks implement the same
asynchronous contracts and terminal behavior as production.

## Phase 9 — Feature migration and hardening

Migrate API Agent first, then Test Agent, then AI Workspace. Preserve their feature-specific decisions while
removing local lifecycle duplication. Test duplicate runs, queued/running cancellation, worker crashes, process
restart, SSE loss/replay, repository exclusivity, tenant fairness, timeouts, cleanup and exactly-once terminal state.

## Phase 10 — End-to-end documentation and operational handoff

Documentation is a release requirement, not a post-release note. It is completed only after verified behavior
and must describe the implemented code rather than the original proposal.

### Shared documentation deliverables

1. System context and component diagrams for browser, API control plane, task/event stores, workers, repositories,
   LLM services and command execution.
2. End-to-end sequence diagrams for Run, progress, review, completion, failure, cancellation, reconnect, retry,
   worker loss and page refresh/resume.
3. Canonical task/event/error/result schemas with example REST and SSE payloads.
4. State-machine reference listing every legal transition, owner, precondition, side effect and terminal rule.
5. Thread, process, worker, semaphore and distributed-lease architecture with configured limits and rationale.
6. Cancellation checkpoint map showing which operations are immediately, cooperatively or timeout cancellable.
7. SSE replay and polling algorithm, event ordering, cursor handling, heartbeat, retry and stale-event rejection.
8. Security model covering tenant/repository authorization, event access, secrets, command sandboxing and auditing.
9. Observability reference covering correlation IDs, logs, metrics, traces, dashboards, alerts and redaction.
10. Capacity and tuning guide for worker count, queue depth, semaphores, timeouts, buffers and backpressure.
11. Failure and recovery runbooks for stuck tasks, lost workers, unavailable stores, stale leases, failed cleanup,
    partial writes, event gaps and poisoned/repeated tasks.
12. Deployment, migration, rollback and compatibility guidance for single-process and distributed environments.

### Per-feature end-to-end documentation

Each of Test Agent, API Agent and AI Workspace must contain a feature-specific guide that traces:

```text
frontend button
 -> facade/store
 -> REST task creation
 -> dispatcher and worker claim
 -> feature orchestrator stages
 -> progress/event persistence
 -> SSE and polling reconciliation
 -> cancellation checkpoints
 -> validation/review/result
 -> frontend terminal state
```

The guide must name actual files, classes, routes, DTOs, task handlers, event producers, stores, components and
configuration keys. Test Agent additionally traces Playwright generation; API Agent traces scenario and code
generation plus MockStubPlan; AI Workspace traces Ask/Agent, tools, staged review and transactional Apply.

### Required traced scenarios

- Successful run from click through rendered result
- Cancellation while queued
- Cancellation during repository discovery
- Cancellation during model/tool/test execution
- Validation failure followed by bounded repair
- SSE disconnect with polling recovery and event replay
- Browser refresh during an active task
- API or worker restart with durable recovery
- Two tasks targeting the same repository
- Per-tenant limit/backpressure behavior
- Needs-review result and approved continuation
- Terminal failure with cleanup and retry

### Documentation verification gate

Documentation is accepted only when links and diagrams render, payload examples pass schema validation, routes and
file names exist, configuration defaults match code, runbooks are exercised in a staging/game-day test, and a new
engineer can execute the local mock flow and one real end-to-end flow without undocumented knowledge.

Update documents in the same pull request as contract, state-machine or operational changes. CI should detect
broken links, stale generated schema references and missing documentation updates for changed public contracts.
