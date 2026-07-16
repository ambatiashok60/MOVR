# Detailed stage and sub-stage decision catalog

This catalog expands document 08. Every sub-stage produces evidence or a decision consumed later.
`Review` means continue with an explicit warning/artifact unless repository policy requires a stop.

## T0 — Admission and request shaping

### T0.1 Authenticate and authorize

- Input: principal, tenant, repository identifier and requested operation.
- Check: tenant membership, repository access and generation permission.
- Decision: accept only an authorized repository binding; never trust a client-supplied filesystem root.
- Output: `AuthorizedWorkspaceContext`.
- Failure: reject before reading repository content.

### T0.2 Normalize intent payload

- Input: story, acceptance criteria, selected files, branch and optional constraints.
- Check: required fields, size, encoding, duplicates and contradictory constraints.
- Decision: preserve user language but create a canonical normalized request and hash.
- Output: `GenerationRequest` plus request hash.
- Reuse: same normalized request, policy and repository revision.

### T0.3 Resolve policy and budget mode

- Check restricted paths, maximum patch scope, command execution permission and `review|strict` usage mode.
- Output: immutable policy snapshot referenced by every later artifact.
- Review: high token estimate is advisory in review mode; strict mode alone blocks.

## T1 — Workspace snapshot and freshness

### T1.1 Resolve revision and dirty state

- Capture branch, commit, working-tree state and file hashes.
- Decide whether generation uses the current working tree, isolated copy or detached worktree.
- Reject a revision change during snapshot construction.

### T1.2 Apply path and data-governance filters

- Exclude secrets, binaries, ignored paths, oversized files and policy-restricted content.
- Record exclusions so later absence is not misinterpreted as proof that a dependency does not exist.

### T1.3 Load or invalidate inventory

- Cache key: repository, revision, policy version, parser versions and relevant working-tree hashes.
- Reuse compatible file-level artifacts; invalidate changed files and dependent graph neighborhoods.

## T2 — Technology and source discovery

### T2.1 Detect package/build system

- Inspect package manifests, lockfiles, Playwright config and scripts.
- Rank evidence; a lockfile alone does not prove the active command.
- Output: technology profile with evidence and confidence.

### T2.2 Parse TypeScript modules

- `ts_ast_parser_tool.py` extracts imports, exports, declarations, calls and source spans.
- Unresolved aliases/dynamic imports remain explicit unresolved edges.

### T2.3 Parse Angular structure

- `angular_parser_tool.py` relates routes, components, templates, bindings and selectors.
- Generated routes or runtime providers are recorded as uncertain rather than inferred as fact.

### T2.4 Parse Playwright structure

- `playwright_parser_tool.py` extracts suites, hooks, tests, fixtures, page objects and locators.
- Output is normalized before use by prompts.

### T2.5 Build typed dependency graph

- Merge parser artifacts into file/symbol nodes and typed edges.
- Deduplicate equivalent edges by source span and target identity.
- Output: graph revision and unresolved-edge report.

## T3 — Existing behavior inventory

### T3.1 Classify test files and helpers

- Distinguish specs, fixtures, page objects, utilities, setup and generated output.
- Do not treat every `.ts` file under tests as a spec.

### T3.2 Extract behavioral test units

- Normalize actor, precondition, action, state transition and assertion.
- Associate each unit with its source test and helper dependencies.

### T3.3 Detect equivalent and overlapping coverage

- Compare semantic behavior, not titles alone.
- Decision: exact coverage blocks duplicate creation; partial overlap becomes reuse/extension evidence.

### T3.4 Determine staleness

- Compare referenced routes, symbols and locators against the current graph.
- Stale tests are evidence, not automatically safe extension targets.

## T4 — Functional-intent reasoning

### T4.1 Decompose acceptance criteria

- Produce actors, initial states, actions, expected states, negative paths and non-functional constraints.

### T4.2 Resolve ambiguity from repository evidence

- Prefer current source and explicit acceptance criteria over naming guesses.
- Preserve unresolved questions with confidence and impact.

### T4.3 Select testable behavior boundaries

- Combine steps only when they represent one independently valuable behavior.
- Avoid creating one test per sentence or one giant end-to-end journey.

### T4.4 Map behavior to source and route evidence

- Link every intended assertion to components/routes/API behavior where possible.
- Missing links raise review confidence; they do not trigger invented selectors.

## T5 — Candidate, placement and ownership decisions

### T5.1 Rank existing specs/helpers

- Score feature match, ownership, setup compatibility, behavior overlap, graph distance and staleness.
- Output ranked candidates with explanations, not only a winning path.

### T5.2 Decide extend versus create

- Extend when ownership and setup are compatible and cohesion improves.
- Create when behavior has a distinct owner or extension would create a mixed-purpose spec.

### T5.3 Resolve destination path

- Follow existing source-root, feature-directory and naming conventions.
- New directories require stronger evidence than new files in established locations.

### T5.4 Resolve helper/page-object ownership

- Reuse the narrowest existing abstraction with compatible semantics.
- Do not move shared helpers merely to support one generated test.

## T6 — Action, flow and locator decisions

### T6.1 Choose create/update/skip

- Skip exact existing coverage; update stale/partial coverage only when ownership is clear; otherwise create.

### T6.2 Merge compatible flows

- Require common actor, setup, state and diagnostic value.
- Reject merging when one failure would obscure which behavior broke.

### T6.3 Select locator candidates

- Rank repository test IDs, accessible roles/names, stable labels and existing page-object methods.
- Reject positional, generated-class and brittle DOM-chain locators unless no safe alternative exists.

### T6.4 Plan assertions and waits

- Prefer user-visible state and Playwright auto-waiting.
- Fixed sleeps require explicit review evidence.

## T7 — Generation and patch construction

### T7.1 Assemble minimal context

- Include intent, destination, relevant graph neighborhood, conventions and reusable examples.
- Exclude unrelated repository content already summarized in artifacts.

### T7.2 Generate structured candidate

- Validate model output against schemas; permit one format repair without changing product intent.

### T7.3 Normalize imports and formatting

- Reuse repository import style and avoid adding unused dependencies.

### T7.4 Build patch plan

- Enumerate create/update operations, base hashes, expected symbols and scope.

### T7.5 Enforce patch guards

- Reject traversal, restricted files, unexpected deletion, excessive scope and stale base hashes.

## T8 — Proof, repair and result

### T8.1 Syntax validation

- Validate every changed source before framework rules.

### T8.2 Playwright quality validation

- Check locators, assertions, waits, isolation, fixtures and test structure.

### T8.3 Repository-command resolution

- Discover the narrowest trusted lint/typecheck/test command; never invent an unsafe shell command.

### T8.4 Optional execution

- Run only when enabled in a controlled workspace; capture command, duration, output summary and environment.

### T8.5 Classify failure

- Separate generated-code defect, repository baseline failure, environment failure and inconclusive result.

### T8.6 Bounded repair

- Repair only the evidence-backed defect; preserve accepted intent and unrelated files.
- Stop after the configured limit or repeated failure signature.

### T8.7 Build review and traceability result

- Return decisions, evidence IDs, files/diff, validation, coverage delta, confidence, usage estimate and warnings.
- Downstream Apply must recheck base hashes and authorization.
