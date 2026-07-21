# Decision specifications and traced execution

## Decision record contract

Every non-trivial decision should be persisted with: `decisionId`, `decisionType`, `stage`, `inputArtifactIds`,
`candidateOptions`, `selectedOption`, `evidence[]`, `rejectedOptions[]`, `confidence`, `policyVersion`,
`producerVersion`, `repositoryRevision`, `reviewReason`, and `downstreamConsumers`. Evidence contains a file,
source span, parser/scanner, observation hash and freshness. This makes a result reproducible and prevents a
later stage from silently replacing an earlier decision.

## Evidence and precedence rules

1. Authorization and repository policy override every other input.
2. Explicit acceptance criteria override inferred naming conventions.
3. Current parsed repository evidence overrides memory and prior generated manifests.
4. Established local test convention outweighs generic framework best practice when safe.
5. Compiler/parser evidence outranks text-search inference; unresolved dynamic behavior remains uncertain.
6. Validation evidence outranks model self-assessment.
7. A reviewer decision applies only to the exact patch/decision revision reviewed.

Confidence is not a decorative score. Record factor scores for evidence completeness, agreement, freshness,
ownership match and unresolved risk. The minimum critical factor should cap the aggregate: high average
confidence cannot hide missing ownership or a brittle locator. Thresholds are configuration, not prompt text.

## State machine and invariants

```text
accepted -> discovering -> deciding -> generating -> validating
  -> repairing -> validating
  -> needs_review | completed | failed | aborted
```

- Only one terminal state is allowed.
- Generation cannot precede placement/action/ownership decisions.
- A changed repository revision invalidates write and execution artifacts.
- `notRun` is never converted to `passed`.
- Repair cannot expand the approved behavior or file scope without a new decision.
- Apply is external/host-controlled and must re-authorize and compare hashes.

## Fully traced example

Request: “Verify the user can filter orders by status.” T0 binds the repository and normalizes the story.
T1 creates snapshot `r17`. T2 parses Angular route/component/template evidence and existing Playwright specs.
T3 finds an orders fixture, page object and a test for date filtering. T4 produces behavior `filter(status) ->
visible rows all match status`; empty-state behavior is a separate candidate. T5 ranks the existing orders
spec above a new file because feature ownership, setup and route match. T6 chooses `update`, reuses the page
object’s status combobox and role-based row locator, and refuses to merge the empty-state scenario because its
expected state differs. T7 generates one test and a page-object method only if the method is absent, then guards
both base hashes. T8 syntax and Playwright-quality checks pass; targeted execution is disabled, so execution is
`notRun`. The result is `needsReview=false` only if policy allows static-only completion; otherwise it explicitly
requests execution review. Traceability links acceptance criterion → behavior → spec/test → assertion.

## Failure matrix

| Failure | Owner | Retry/repair | Terminal/review outcome |
|---|---|---|---|
| schema-format response | LLM boundary | one structured repair | fail after repeated invalid output |
| unresolved owner | discovery/decision | gather bounded evidence | review; do not guess placement |
| stale base hash | workspace | no model repair | conflict review/restart snapshot |
| syntax/quality defect | generated patch | bounded repair | review/fail after repeated signature |
| baseline test failure | repository | no patch repair unless causally linked | review with baseline evidence |
| environment unavailable | execution | optional controlled retry | inconclusive/notRun, never pass |

## Change-review questions

For every workflow modification ask: Which artifact contract changes? Which downstream consumers break? Does
the decision precedence change? Is cache invalidation still correct? Can the new stage mutate authority? Does
it duplicate existing evidence? Which invariant and golden trace prove the behavior?
