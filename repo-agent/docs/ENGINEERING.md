# Engineering and contribution guide

This guide defines how changes move from an idea to production-ready code. It
optimizes for small, reversible decisions and evidence that matches risk.

## 1. Before changing code

1. State the user-visible outcome and non-goals.
2. Identify the affected boundary: API/SSE contract, security, persistence,
   workspace mutation, provider, or UI state.
3. Read the relevant module and tests; do not infer behavior from docs alone.
4. Decide whether the choice needs an ADR using [the ADR guide](adr/README.md).
5. Define acceptance criteria as tests, then follow [the TDD playbook](TESTING.md).

## 2. Architectural constraints

- API routes remain thin; lifecycle behavior belongs in a service.
- The orchestrator coordinates. It does not bypass tool authorization,
  `PathGuard`, snapshots, validation, or the event bus.
- The LLM proposes actions; deterministic server code authorizes and executes.
- All settings belong in `app/config.py` and use the `REPO_AGENT_` prefix.
- New providers implement `LLMClient`; provider-specific logic does not leak into
  orchestration.
- Persistence goes through repositories. HTTP handlers and UI code do not issue
  database operations.
- Shared enum/event changes are atomic across backend, both frontends, tests, and
  `integration-contract.md`.
- A run must reach exactly one terminal state: completed, failed, or cancelled.

## 3. Change workflow

Keep changes vertically sliced and independently reviewable:

1. Add the failing acceptance test at the narrowest useful layer.
2. Add or change the domain model and contract.
3. Implement persistence/service behavior.
4. Wire the API/event surface.
5. Update the frontend only after the contract is executable.
6. Exercise failure and recovery paths.
7. Update docs, operational signals, and an ADR when applicable.

Separate mechanical refactors from behavior changes where practical. Avoid
combining dependency upgrades, broad formatting, and feature logic in one review.

## 4. Definition of done

A change is done when:

- acceptance criteria are covered by deterministic tests;
- the full affected test layers pass;
- Ask/Agent permissions and path boundaries remain server-enforced;
- errors are typed/actionable and runs remain terminal/recoverable;
- observability exposes enough context to diagnose the new failure modes;
- API/SSE and configuration documentation is current;
- deployment and rollback implications are written down;
- no credentials, generated caches, databases, or dependency directories are
  included in the change.

## 5. Pull request narrative

Use this shape so reviewers can evaluate the decision rather than reconstruct it:

```markdown
## Outcome
What user/system behavior changes?

## Scope and non-goals
What is deliberately excluded?

## Design
Which boundary owns the behavior? Link an ADR when required.

## Evidence
What failed before the fix? Which tests and manual checks passed?

## Risk and recovery
Security, data, concurrency, compatibility, rollout, and rollback.

## Documentation
Changed docs, or why no documentation change is required.
```

Reviewer order: contract and threat boundary, failure modes, tests, production
code, then maintainability. A green happy-path test does not outweigh a missing
authorization or recovery case.

## 6. Compatibility and evolution

- Prefer additive API/event fields. Consumers must ignore unknown fields.
- Never repurpose an existing enum or error code with different semantics.
- Event ordering and idempotency are public behavior.
- Database changes require a forward migration and a rollback/compatibility plan
  before the project moves beyond its current bootstrap schema.
- Config renames require a documented transition period or an explicit breaking
  release.

## 7. Dependency policy

Add a dependency only when its lifecycle and risk are cheaper than maintaining
the capability locally. Document why it is needed, pin a compatible range, and
review license, provenance, maintenance activity, known vulnerabilities, image
size, and runtime permissions. Provider SDKs should remain optional when their
provider is optional.
