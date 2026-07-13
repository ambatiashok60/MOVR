# Implementation Plan

## Current Baseline

Already implemented:

- Angular 18 shell with workspace, chat, multi-file checkbox selection, and
  review panels.
- FastAPI service with `.env` configuration.
- Backend-only AWS SSO profile, region, and Claude Sonnet 4.5 integration.
- Allowed-root enforcement, safe path resolution, exclusions, bounded reads,
  file listing, and Git detection.
- Proposal contracts, unified diff generation, selective file apply, atomic
  replacement, and stale-file hash checks.
- Bounded Bedrock Converse tool loop with workspace file listing, text search,
  range reads, exact replacements, file creation, and deletion.
- Tool-generated proposals connected to Angular file-level diff review and
  selective apply.
- Approval-gated one-run transformation proposals executed in a constrained,
  timed child process against in-memory text files.
- Reviewed persistent custom tools stored under the filesystem state directory
  and exposed to later Bedrock runs through typed tool schemas.
- Initial Python safety tests and strict TypeScript checking.

Not yet production-grade:

- Tool events are returned after completion rather than streamed live through
  durable SSE events.
- Review is currently file-level; hunk-level acceptance is not implemented.
- Proposal state is in memory rather than durable filesystem storage.
- Large-file symbol indexing, retrieval, streaming, hunk review, rollback,
  validation tools, and resumable migration batches remain to be implemented.

## Phase 1: Durable Filesystem Foundation

- Add atomic JSON/JSONL filesystem repositories for workspaces, sessions,
  messages, runs, events, proposals, review decisions, and apply journals.
- Store content-addressed file snapshots separately so unchanged source content
  is not duplicated across runs.
- Use per-session/run directories, temporary-file replacement, file locks, and
  schema versions so interrupted writes remain recoverable.
- Replace in-memory proposal storage.
- Add stable workspace IDs instead of sending raw paths on every request.
- Add structured API errors, request IDs, and redacted structured logs.
- Extend tests for symlinks, concurrent changes, encodings, permissions, and
  partial apply failure.

Exit criteria: restart-safe filesystem sessions and proposals with atomic
apply/rollback and no SQL dependency.

## Phase 2: Workspace Intelligence

- Implement incremental scanning using file hashes and project ignore rules.
- Add directory selection, bulk selection, pinned files, strict/guided scope,
  file search, and scope estimates in Angular.
- Add large-file range reads and structural chunking.
- Add language adapters for TypeScript/JavaScript, Python, HTML/CSS, JSON/YAML,
  and common migration configuration files.
- Build symbol outlines and import/reference graphs, with lexical search as the
  always-available baseline.

Exit criteria: relevant context can be found without loading entire large files
or repositories into one model request.

## Phase 3: Complete the Bedrock Agent Runtime

- Upgrade the implemented Converse tool loop to ConverseStream.
- Persist and emit every action as a durable SSE event.
- Add symbol outlines, reference lookup, dependency graph, and validation tools
  to the existing typed tool registry.
- Implement context budgets, result compaction, cancellation, retry policy,
  model timeout, step limits, and SSO-expiry recovery.
- Add mocked Bedrock transcripts for deterministic agent-loop tests.

Exit criteria: Sonnet 4.5 can independently explore selected and related files,
update its plan, and answer with evidence across multiple tool turns.

## Phase 4: Proposal Editing and Review

- Create an isolated proposal workspace with copy-on-write file snapshots.
- Add create, targeted patch, rename, delete, and format tools.
- Connect model tool calls to proposal generation.
- Add Angular unified/side-by-side diffs, file and hunk selection, change groups,
  syntax highlighting, sensitive-file warnings, and revision requests.
- Add conflict detection, partial apply, full rollback, and post-apply Git diff
  display when available.

Exit criteria: a user can complete a multi-file migration without any unreviewed
write reaching the real workspace.

## Phase 5: Migration Validation Loop

- Detect package managers, build systems, language versions, and likely focused
  validation commands.
- Add policy-controlled format, lint, type-check, test, and build tools.
- Run commands in the proposal workspace with time, output, environment, and
  working-directory limits.
- Feed compact failure diagnostics back into the agent for bounded repair loops.
- Present validation evidence and unresolved failures with each diff group.

Exit criteria: the agent edits, validates, diagnoses, repairs, and reports a
coherent migration batch before user approval.

## Phase 6: Scale, Quality, and Operations

- Add resumable batch migrations, checkpoints, background run workers, and SSE
  reconnection.
- Add cost/latency/token telemetry and per-run budgets.
- Add golden migration fixtures and evaluation cases for Angular, Python,
  dependency upgrades, API renames, configuration changes, and non-Git folders.
- Add adversarial tests for prompt injection in source files, path attacks,
  secret exfiltration, destructive edits, oversized output, and command abuse.
- Add accessibility, responsive behavior, keyboard review, and performance
  profiling for large trees and diffs.

Exit criteria: repeatable migration quality, recoverable runs, observable cost,
and enforced safety boundaries.

## Quality Gates for Every Phase

- Unit and integration tests for all new backend policies and state transitions.
- Strict Angular compilation and component tests.
- No direct filesystem write from the model invocation path.
- No AWS profile or credential material in frontend responses or logs.
- Every edit has an original hash, proposed content, diff, decision, and apply
  record.
- Large-workspace tests use realistic generated fixtures rather than only tiny
  files.
