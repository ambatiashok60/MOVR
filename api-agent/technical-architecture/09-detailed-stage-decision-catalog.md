# Detailed stage and sub-stage decision catalog

## A0 — Admission, workspace and policy

### A0.1 Authorization

Bind principal, tenant, repository and branch through host dependencies. Reject before discovery when
the binding is invalid. Request paths never become trusted workspace roots.

### A0.2 Snapshot and locking

Capture revision, dirty state and relevant hashes. Code-generation mutations require the repository
lock; scenario-only discovery may use a read snapshot.

### A0.3 Policy and budget

Resolve restricted paths, execution permission, infrastructure rules and review-first usage thresholds.
Persist the policy version with every decision.

## A1 — Story intake and interpretation

### A1.1 Normalize story

Extract title, narrative, acceptance criteria, constraints and linked API hints. Remove duplicate text
without losing source references.

### A1.2 Identify ambiguity

Classify missing actor, operation, input, output, error, authorization, state and environment details.
Repository evidence may resolve ambiguity; guesses remain review flags.

### A1.3 Derive coverage dimensions

Create candidates for positive, negative, contract, security, boundary, idempotency, concurrency and
dependency failure behavior only where story/repository evidence makes them relevant.

## A2 — Repository and API discovery

### A2.1 Build/build-tool discovery

Inspect manifests, dependencies, plugins, source roots and test commands. Rank active conventions over
mere installed dependencies.

### A2.2 Endpoint discovery

Scan controllers/routes, HTTP annotations and application registration. Preserve source spans and method.

### A2.3 OpenAPI reconciliation

Match operation ID, path, method, parameters and schemas against source endpoints. Record drift rather
than silently preferring either source.

### A2.4 DTO/schema discovery

Link request/response models, validation constraints, serialization and error envelopes.

### A2.5 Dependency discovery

Identify databases, HTTP clients, messaging, authentication, caches and infrastructure configuration.
Static absence is not proof of runtime absence.

### A2.6 Existing-test/helper/fixture discovery

Catalog framework, placement, base classes, utilities, data factories, mocks/stubs and command patterns.

### A2.7 Produce RepoProfile and SourceContext

Deduplicate scanner facts, resolve conflicts by evidence strength and retain unresolved items/confidence.

## A3 — Scenario generation decisions

### A3.1 Select operation scope

Map story behaviors to known operations. Multiple operations remain separate unless one scenario
specifically validates their transaction or sequence.

### A3.2 Create scenario candidates

Each candidate includes preconditions, request, expected response/state, category, priority and evidence.

### A3.3 Deduplicate candidates

Compare operation, state, input partition and expected outcome—not scenario titles.

### A3.4 Score value and priority

Use business impact, failure likelihood, contract/security risk, coverage gap and execution cost.

### A3.5 Select target

Choose CI, stage or both from dependency/environment needs. Host stage configuration is mandatory for
stage claims; otherwise mark review.

### A3.6 Persist reviewable scenario set

Scenario IDs are stable across presentation changes. Regeneration references superseded decisions.

## B0 — Code-generation refresh

### B0.1 Verify selected scenario

Require a current, authorized scenario and preserve its approved intent.

### B0.2 Refresh affected graph neighborhood

Re-scan endpoint, DTO, client, tests and dependencies touched since scenario creation. Avoid a global scan
when revision-aware evidence remains fresh.

### B0.3 Detect scenario drift

If method/path/schema or expected behavior changed, stop for review or explicitly regenerate the scenario.

## B1 — Strategy, placement and command selection

### B1.1 Rank strategies

Use build dependencies, existing tests, source roots and commands. Installed-but-unused libraries have
lower weight than established tests.

### B1.2 Select Spring/Python mechanism

Prefer existing RestAssured, MockMvc, WebTestClient, WebClient seam, pytest-httpx or TestClient pattern.
Adding a new framework requires review.

### B1.3 Select placement and naming

Follow package/module ownership and adjacent tests. Detect create versus update conflicts.

### B1.4 Resolve narrow validation command

Prefer targeted test task, then module task, then broader suite when trusted and allowed.

## B2 — Mock and stub planning

### B2.1 Classify dependencies

For each dependency record local/in-process/external, synchronous/asynchronous, controllability and risk.

### B2.2 Discover reusable mechanisms

Prefer existing fixtures, WireMock mappings, Mockito helpers, MockWebServer setup, containers and factories.

### B2.3 Select mechanism

Choose a repository-supported mechanism that proves the scenario with least infrastructure impact.

### B2.4 Determine supporting files

List exact create/update operations, expected symbols and lifecycle/cleanup behavior.

### B2.5 Assign confidence, approval and unresolved promises

Authentication, infrastructure and stage-impacting plans require stronger evidence. Missing promised
supporting files trigger regeneration, then `needsReview` after the bounded limit.

## B3 — Generation, mutation and proof

### B3.1 Assemble context and plan

Include scenario, strategy, relevant source graph, conventions and MockStubPlan; exclude unrelated files.

### B3.2 Generate structured files

Require paths, content, purpose and relationships. Schema-format repair does not authorize intent changes.

### B3.3 Guard files

Reject traversal, restricted paths, unexpected deletions, stale base hashes and excessive scope.

### B3.4 Validate promised artifacts

Verify referenced fixtures, stubs, resources and helpers exist in generated or repository files.

### B3.5 Static/framework validation

Check syntax, imports, framework structure, assertions, cleanup, contracts and mock lifecycle.

### B3.6 Optional execution

Execute only trusted allowlisted commands in a controlled workspace; `notRun` remains distinct from pass.

### B3.7 Failure classification and bounded repair

Separate generated defect, baseline failure, environment failure, dependency unavailability and inconclusive
result. Repair only generated defects supported by validation evidence.

### B3.8 Commit candidate result

Return files, diff, scenario traceability, strategy, MockStubPlan, validation, usage and review decisions.
Actual production writes follow host approval and repository transaction policy.
