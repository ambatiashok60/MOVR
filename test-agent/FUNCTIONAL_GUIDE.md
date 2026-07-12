# Test Agent — Functional Guide

## Purpose

Test Agent turns a completed user story or functional-test request into repository-native
Playwright coverage. It analyzes the target frontend, decides whether to create, append, or extend
tests, generates guarded patches, validates them, and returns a reviewable result.

## Primary user flow

```text
Story/test request
→ select repository and branch
→ inspect frontend and existing Playwright tests
→ understand functional intent
→ map intent to UI sources/routes/locators
→ classify existing behavioral coverage
→ decide create/append/extend
→ choose target spec and ownership
→ generate patches
→ critic and safety review
→ apply in isolated workspace
→ validate and repair
→ coverage/value/traceability review
→ return files, diff, evidence and risks
```

## Functional stages

1. **Request normalization** — captures repository, story/test name, steps, tenant and job ID.
2. **Repository strategy** — detects Playwright support, greenfield bootstrap needs and validation commands.
3. **Technology intelligence** — identifies Angular/React/Vue and Playwright conventions.
4. **Inventory** — indexes specs, page objects, fixtures, helpers, routes and source fingerprints.
5. **Idempotency** — avoids generating an equivalent patch twice against the same repository state.
6. **UI intelligence** — discovers components, routes, locators, mocks and authentication patterns.
7. **Functional intent** — converts story language into business behaviors and assertions.
8. **Source mapping** — grounds desired behavior in real repository files and UI elements.
9. **Behavior inventory** — compares against what existing tests already prove.
10. **Placement** — selects the correct spec file or a safe new spec location.
11. **Action decision** — chooses create, append or extend using evidence and confidence.
12. **Ownership and locators** — decides what belongs in page objects/fixtures/specs and selects stable locators.
13. **Patch generation** — creates complete repository-native changes.
14. **Critic and guards** — checks imports, references, promises, structure and unsafe edits.
15. **Validation/repair** — runs repository commands when enabled and repairs bounded failures.
16. **Enterprise review** — reports coverage preservation, test value, traceability, policy, budget and manifest.

## Decision rules

- Existing nearby conventions outrank generic best practice.
- Extend only when the existing test context is complete and confidence is sufficient.
- Append when a related spec exists but extension would weaken or distort existing behavior.
- Create only when placement evidence supports a new test/spec.
- Full duplicates and low-value tests are review findings.
- Cost/token thresholds are review estimates by default, not blockers.
- Restricted repository files never enter model prompts.

## Output

The final result includes changed files, unified diff, decision traces, validation, coverage,
test-value classification, traceability, review report, generation manifest, budget usage,
confidence and remaining risks.

## Current scope

This repository is backend-focused. It does not own the Worktop Angular page. A host frontend
should display progress, plan, diffs, review reasons and Apply controls using the host API envelope.

