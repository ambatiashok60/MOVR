# Detailed stage and sub-stage decision catalog

## W0 — Entry, authority and session

### W0.1 Authenticate and bind tenant

Resolve identity and tenant through trusted host dependencies. Reject spoofed request tenancy.

### W0.2 Authorize repository and operation

Separate read/Ask, Agent staging, command execution, sensitive-file and Apply permissions.

### W0.3 Validate workspace

Resolve repository, branch, revision, root containment, dirty state and supported VCS behavior.

### W0.4 Create or resume session

Load messages, selected context, goal and prior decisions. A resumed session must verify repository
revision and mark stale artifacts.

### W0.5 Resolve mode

Ask for explanation/diagnosis/read-only planning; Agent for requested implementation. Ambiguous mutation
authority stays Ask or requests review instead of assuming write permission.

## W1 — Goal and constraint construction

### W1.1 Normalize user goal

Create outcome, acceptance evidence and explicit non-goals without losing the original prompt.

### W1.2 Extract constraints

Capture selected files, technologies, commands, time/iteration/usage policy and forbidden actions.

### W1.3 Detect missing success criteria

Use repository conventions for minor details. Materially different outcomes require user review.

### W1.4 Create goal artifact

Version the goal so later plan changes can name which requirement caused them.

## W2 — Repository context and code graph

### W2.1 Capture snapshot

Record revision and hashes; use an isolated workspace for Agent mutations.

### W2.2 Load instruction hierarchy

Resolve repository, directory and task instructions with provenance and precedence.

### W2.3 Retrieve selected files

Selected files are high-priority context, not permission to ignore their dependencies.

### W2.4 Query file/symbol graph

Find definitions, inbound/outbound references, routes, components, DTOs and tests. Until a compiler-backed
provider exists, label search/model-derived relationships with lower confidence.

### W2.5 Retrieve memory

Load relevant decisions/conventions by scope and freshness. Current repository evidence overrides memory.

### W2.6 Rank and budget context

Prefer goal relevance, graph distance, ownership, recency and evidence quality. Summarize large artifacts
while preserving source references and unresolved questions.

### W2.7 Detect context gaps

List named uncertainties such as entry point, owner, caller, contract, expected test or command.

## W3 — Ask-mode reasoning

### W3.1 Build evidence-backed prompt

Include goal, constraints, relevant artifacts and citation/source handles.

### W3.2 Decide whether more reads are needed

Use the least-powerful read/search/list action that closes a named gap; avoid repeated equivalent searches.

### W3.3 Produce answer

Separate fact, inference, recommendation and uncertainty. Ask mode produces no patch/write tool call.

### W3.4 Persist conversation summary

Store compact goal/evidence/decision references, not an unbounded duplicate of repository content.

## W4 — Agent planning

### W4.1 Build initial impact hypothesis

Identify likely entry points, affected symbols, callers, DTOs, routes, tests and configuration.

### W4.2 Create ordered plan

Each step names objective, dependencies, evidence required, allowed tools and completion proof.

### W4.3 Run evidence gate

Mutation is blocked until target ownership, base revision, affected contract and validation path are known.

### W4.4 Publish plan state

Persist and emit plan version so UI, events and review reference the same plan.

## W5 — Tool decision loop

### W5.1 Select next uncertainty

Choose the highest-impact unresolved item that blocks a downstream plan step.

### W5.2 Select least-powerful tool

Prefer read over search expansion, search over execution, and staged write over direct Apply.

### W5.3 Validate tool input

Enforce path containment, argument schema, permission, command allowlist and timeout.

### W5.4 Detect duplicate tool call

Compare normalized tool/input/snapshot with observations. Repeat only when a changed artifact or new question
changes expected information value.

### W5.5 Execute and capture observation

Record bounded output, source, duration, status and redactions. Tool output is evidence, not automatically truth.

### W5.6 Update graph/context and confidence

Add resolved relationships, invalidate contradicted assumptions and re-rank context.

### W5.7 Re-plan or stop

Continue when information gain advances a plan step. Stop for review on repeated failure, missing authority,
unsafe external dependency, or exhausted limit. Usage limits are review-first unless strict policy applies.

## W6 — Patch design and isolated mutation

### W6.1 Freeze intended change set

Name files, symbols, contract changes, tests and expected behavior before writing.

### W6.2 Check inbound impact

Review callers, routes, injected consumers, DTO mappings and tests. Public-contract uncertainty requires review.

### W6.3 Choose create/update/delete operation

Prefer minimal cohesive changes. Delete/rename requires stronger authority and complete reference evidence.

### W6.4 Stage in isolated workspace

Use base hashes and prohibit writes outside authorized roots.

### W6.5 Generate normalized diff

Exclude unrelated formatter churn and expose every changed file to review.

## W7 — Validation and repair

### W7.1 Static checks

Validate syntax, types/imports where available, paths, file size and restricted content.

### W7.2 Select tests/commands

Use affected graph nodes and repository conventions to choose the narrowest trusted proof.

### W7.3 Execute when authorized

Capture environment and distinguish pass, fail, timeout, unavailable and not-run.

### W7.4 Classify failure

Separate patch defect, repository baseline, environment, flaky/inconclusive and external-service failure.

### W7.5 Bounded repair

Use validator evidence and preserve goal/accepted changes. A repeated signature or behavioral redesign exits
to review rather than continuing autonomously.

### W7.6 Engineering review score

Evaluate correctness evidence, contract risk, test proof, maintainability, security and unresolved uncertainty.

## W8 — Human review and Apply

### W8.1 Present review package

Show plan, evidence, files/diff, validation, commands, usage, warnings and unresolved decisions.

### W8.2 Record per-change decisions

Keep/reject/revise decisions bind to patch revision and reviewer identity.

### W8.3 Reconcile dependent decisions

Rejecting a foundational file invalidates dependent changes; never apply a structurally incomplete subset.

### W8.4 Pre-Apply conflict check

Reacquire lock and compare current hashes with staged base hashes.

### W8.5 Transactional Apply

Journal, snapshot, write atomically and verify final hashes. Roll back on partial failure.

### W8.6 Finalize execution

Emit one terminal state, audit outcome, invalidate changed graph nodes and store concise reusable learnings with
provenance. SSE and polling read the same state owner; neither independently decides completion.
