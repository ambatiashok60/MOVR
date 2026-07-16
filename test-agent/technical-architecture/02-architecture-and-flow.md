# Architecture and execution flow

## Design foundation

The model interprets ambiguous repository evidence. Deterministic code owns path safety, policy,
inventory, budgets, patching, validation, and review outcomes.

```text
FastAPI route
  -> GenerationOrchestrator
  -> technology adapter and repository inventory
  -> intent / placement / ownership / locator decisions
  -> Playwright generation
  -> guarded patch plan
  -> validation and bounded repair
  -> coverage, value, traceability and review result
```

## Detailed stages

1. Normalize the request and verify repository scope.
2. Fingerprint framework, package manager, commands, test layout, helpers, fixtures and page objects.
3. Build behavioral inventory so generation reuses existing flows rather than duplicating them.
4. Resolve target spec, ownership boundaries, locator policy and reusable abstractions.
5. Ask the model for structured output; validate it with Pydantic and allow one schema repair.
6. Convert the proposal into a bounded file plan and reject forbidden paths or oversized changes.
7. Produce a diff, syntax-check it, apply Playwright quality rules and optionally run trusted commands.
8. Attempt bounded repair only when evidence identifies a repairable failure.
9. Return changed files, validation, confidence, budget estimate, coverage and review flags.

Generation should be idempotent: equivalent intent and repository state should not append duplicate
tests. Token budgeting is review-first by default; strict enforcement is an explicit policy choice.
