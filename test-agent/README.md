# Playwright Agent Service

## Executive Summary

`test-agent` is the beta scaffold for a repository-aware Playwright spec
generation backend. It is designed as a FastAPI service that accepts a functional
test case, repository context, and branch context, then produces executable,
maintainable Playwright changes through an agentic workflow.

The intended product behavior is direct repository update for beta: no manual
review gate is required before writing. Even though the service writes directly,
each generation job must return the files changed, diff summary, reasoning,
confidence, and validation result.

Core principle:

```text
LLM decides.
Tools parse.
Backend writes safely.
Validation proves executability.
```

This service is not a simple prompt-to-code generator. The target design is a
repository-aware test engineering agent that uses source code, existing
Playwright tests, page objects, fixtures, helper conventions, and validation
signals to decide where and how to update test coverage.

## What Was Created

This scaffold creates the backend baseline under:

```text
/Users/ashokkumar/Documents/movr/MOVR/test-agent
```

The current implementation includes:

- FastAPI application bootstrap.
- Generation, job, and event route modules.
- Pydantic schemas for generation requests, decisions, repository profile,
  technology profile, inventory, patching, validation, and final result.
- Service modules for every major workflow stage.
- Agent modules for functional intent, source mapping, spec placement,
  candidate ranking, test action decisions, flow merge, ownership resolution,
  locator reasoning, code generation, repair, and critic review.
- `BaseAgent` for common agent behavior.
- Deterministic tool modules for file I/O, search, Git, TypeScript parsing,
  Playwright parsing, Angular parsing, and command execution.
- Inventory cache, inventory builder, dependency map, and file fingerprinting.
- Scoped patch writing for create, replace, and append operations with backup
  creation, patch planning, safe path checks, and unified diff generation.
- Playwright block parsing for `describe(...)` and `test(...)` line ranges.
- Behavioral inventory extraction from real Playwright test blocks.
- Playwright validation for test discovery and duplicate titles within spec
  files.
- Validation placeholders for syntax checks and repo command validation.
- Shared logging metadata helper at `app/utils/logging_utils.py`.
- Repository support classification for beta-fit, warning-fit, and unsupported
  repositories.

The scaffold compiles successfully with:

```bash
python3 -m compileall -q test-agent
```

## Functional Goal

The service generates or updates Playwright E2E specs from a functional test
case. A request contains:

- Job identifier.
- Repository path.
- Branch.
- Tenant identifier when available.
- Functional test case name.
- Natural language steps.
- Validation preference.

The service should inspect the repository and decide whether to:

- Extend an existing Playwright test.
- Append a new test to an existing `describe` block.
- Create a new spec file using the repository convention.
- Add new locators or helper methods to the correct page object, fixture,
  helper, or spec file.

## Supported Repository Scope

Beta support is intentionally focused. The service should first target
conventional TypeScript Playwright E2E repositories where source, specs,
fixtures, helpers, package scripts, and Playwright configuration are locally
available and statically inspectable.

### Primary Beta Targets

The first production-ready path should support:

- Angular applications using TypeScript and Playwright E2E tests.
- React applications using TypeScript and Playwright E2E tests.
- Single frontend app repositories with a clear `src/`, `tests/`, `e2e/`, or
  `playwright/` structure.
- Simple monorepos where app roots and Playwright ownership are obvious.
- Repositories with existing page objects, fixtures, helpers, or stable locator
  conventions.
- Repositories where Git branch and HEAD are locally available.
- Repositories with validation commands available through package scripts.

### Expected Repo Signals

A repo is a good beta fit when it has most of these signals:

```text
playwright.config.ts or playwright.config.js
package.json
package-lock.json, pnpm-lock.yaml, or yarn.lock
tests/, e2e/, playwright/, apps/*/e2e/, or packages/*/tests/
*.spec.ts or *.e2e.ts Playwright specs
src/ application source
optional page object, fixture, helper, or test-data folders
```

### Supported Repo Shapes

```text
Single app frontend repo      Strong fit
Angular + Playwright TS repo  Strong fit
React + Playwright TS repo    Strong fit
Simple monorepo               Supported with clear ownership
Page object based repo        Strong fit
```

### Repos Requiring Additional Adapters

These repository types are not the initial beta target and need more parser,
runtime, or validation support:

- Cypress-only repositories.
- Selenium, WebDriver, Java, Python, C#, Ruby, or non-TypeScript test repos.
- Playwright repos using a custom internal DSL instead of recognizable
  Playwright APIs.
- Complex Nx, Turborepo, Bazel, or polyrepo setups with ambiguous app/test
  ownership.
- Repositories with many Playwright configs and no clear target app.
- Microfrontend repositories where routes and screens are assembled dynamically.
- Apps with little static source evidence for locators or user flows.
- Repositories requiring containers, remote services, secrets, or seeded
  environments before basic validation can run.
- Repositories with strict architecture rules that are not discoverable from
  source code.

### Beta Scope Statement

```text
Beta supports conventional TypeScript Playwright E2E repositories, including
single-app frontend repos and simple monorepos, where Playwright config,
package scripts, source files, existing specs, fixtures, helpers, and page
objects are locally available and statically inspectable.

Beta also supports bootstrap mode: an Angular/React TypeScript UI repository
with NO E2E framework at all is not rejected — the Playwright framework
(config, dependency, e2e/ convention, fixtures entry point, and the first
spec) is scaffolded during generation, governed by Playwright best practices.

Beta does not target Cypress/Selenium repos, non-TypeScript Playwright repos,
highly custom test DSLs, complex build-system monorepos, or repositories
requiring remote infrastructure/secrets for basic validation.
```

### Runtime Scope Enforcement

`RepoStrategyService` classifies every request before the LLM runtime is created.
The generated `RepoProfile` includes:

- `support_status`: `supported`, `supported_with_warnings`, or `unsupported`.
- `requires_bootstrap`: true when the repo is a qualifying Angular/React
  TypeScript UI app with no Playwright framework yet — generation scaffolds the
  framework instead of rejecting the repo. Missing config/specs are only
  blockers when the repo does not qualify for bootstrap (no package.json, no
  beta framework signal, or a competing test framework like Cypress/Selenium).
  A repo with a Playwright config but no specs yet is a warning, not a blocker.
- `support_reasons`: concrete signals that make the repo a beta fit.
- `support_warnings`: risks that may require additional ownership logic.
- `support_blockers`: reasons the repo cannot run through beta generation.
- detected Playwright configs, TypeScript Playwright specs, package manager,
  package scripts, lockfiles, frameworks, monorepo tooling, and unsupported
  framework signals.

Unsupported repositories fail fast with a `422` response:

```json
{
  "error": "unsupported_repository",
  "message": "Unsupported repository for Playwright beta generation: ...",
  "repo_profile": {
    "support_status": "unsupported",
    "support_blockers": []
  }
}
```

Supported repositories continue into the agentic workflow. Repositories marked
`supported_with_warnings` are allowed to continue, but the warnings are returned
in the final `repo_profile`.

## API Design

### Generate Playwright Test

```http
POST /api/playwright/generate
```

Request model:

```json
{
  "job_id": "job-123",
  "repo_path": "/path/to/repo",
  "branch": "feature/example",
  "tenant_id": "tenant-1",
  "test_case_name": "Create order",
  "steps": [
    "Open orders page",
    "Create a new order",
    "Verify order status"
  ],
  "run_validation": true
}
```

Response model:

```json
{
  "job_id": "job-123",
  "files_changed": [],
  "diff_summary": "0 patch(es) generated",
  "confidence": 0.0,
  "needs_review": false,
  "review_reasons": [],
  "decision_trace": [],
  "validation": {
    "passed": true,
    "checks": [
      {
        "name": "syntax",
        "passed": true,
        "output": "deferred"
      }
    ],
    "repair_attempted": false
  }
}
```

### Job Status

```http
GET /api/playwright/jobs/{job_id}
```

Returns job status and final result when persistence is added.

### Event Stream

```http
GET /api/playwright/events/{job_id}
```

Returns an SSE stream for progress events. The current scaffold exposes a
heartbeat response and leaves durable event streaming for the next phase.

## End-to-End Generation Workflow

The intended generation workflow is:

```text
Generate Button
   ↓
FastAPI creates generation job
   ↓
Repo Strategy Profiler
   ↓
Technology Intelligence
   ↓
Test File Classification
   ↓
Repository Inventory Cache
   ↓
Functional Intent Agent
   ↓
Functional Case Reconciliation
   ↓
Source Intelligence
   ↓
Behavioral Test Inventory
   ↓
Spec Placement Agent
   ↓
Candidate Test Ranking Agent
   ↓
Extend / Append / Create Decision Agent
   ↓
Reconcile + Confidence Gate (deterministic)
   ↓
Existing-Test Context (extend) / Anchor Flow Context (append)
   ↓
Flow Stability / Flow Merge Agent (extend, grounded in existing test)
   ↓
Ownership Resolution Agent
   ↓
Locator and Functionality Justification Agent
   ↓
Code Generation Agent
   ↓
Patch Plan Guard (extension target, preserved steps, append reuse,
                  reference integrity, ownership emission, created-spec structure)
   ↓
Scoped Patch Writer
   ↓
Validation Agent
   ↓
Repair Agent
   ↓
Final Response
```

The current scaffold wires these stages through
`app/services/generation_orchestrator.py`. A few stages remain deterministic
placeholders so the system shape is stable before connecting the remaining parser
implementations, but the decision stages themselves are now fully wired (see
[Decision Intelligence Hardening](#decision-intelligence-hardening)).

## Decision Intelligence Hardening

The first iteration wired the stages together but left several of the placement
and test-action decisions loosely enforced. This section documents what changed,
why, and how the new design differs from the original.

### What the old design did

- **Two decisions gated output**: spec placement (`create_new` + target file) and
  the extend/append/create test action. Both were produced by the LLM.
- **Decisions were stringly-typed**: `TestActionDecision.action` was a bare `str`,
  so an out-of-vocabulary action from the model was never rejected at parse time.
- **No confidence gating**: a `0.30` decision flowed into code generation exactly
  like a `0.95` decision. Confidence was logged but never changed behavior.
- **No placement/action reconciliation**: nothing checked that `create_new=false`
  disagreed with an `action` of `create_new_spec`.
- **Candidate ranking was a no-op**: `CandidateTestRankingAgent.rank()` returned
  the candidates in raw inventory order, so `target_test_title` selection and the
  fallback had no evidence-based ordering.
- **Flow merge and ownership resolution were advisory only**: both agents ran, but
  their results were logged and thrown away — they never reached the code
  generation prompt. There was therefore no real "which page object owns this?"
  decision and no "preserve the stable flow, add only the missing steps" signal.
- **The only strongly enforced standard** was the `extend_existing_test` patch
  guard, which requires an exact replace on the selected test block.

### What the new design does

The decision stages are now typed contracts with deterministic guardrails around
the LLM, an evidence-based ranking pass, and the previously discarded advisory
agents wired directly into code generation.

```text
Spec Placement Agent            LLM decision (typed, confidence-bounded)
   ↓
Candidate Test Ranking Agent    LLM ranks candidates by behavioral overlap
   ↓
Extend / Append / Create Agent  LLM decision (Literal action, confidence-bounded)
   ↓
Reconcile action ↔ placement    Deterministic: action must match the target file
   ↓
Confidence gate                 Deterministic: low confidence → safe fallback + flag
   ↓
Existing-test context + guard   Deterministic: extend must target the exact block
   ↓
Flow Merge + Ownership + Locators  Fed into code generation (no longer discarded)
   ↓
Code Generation Agent
   ↓
Patch Plan Guard                Reference integrity, ownership emission,
                                created-spec structure, append reuse,
                                extension target + preserved steps
```

#### 1. Typed decision contracts

- `TestActionDecision.action` is now `Literal["extend_existing_test",
  "append_new_test", "create_new_spec"]`, backed by shared `TestActions`
  constants. An invalid action fails Pydantic validation, which routes the stage
  to its deterministic fallback instead of flowing downstream.
- Confidence on `TestActionDecision`, `SpecPlacementDecision`, and
  `OwnershipResolution` is bounded to `[0, 1]`.

#### 2. Placement ↔ action reconciliation

Placement is the authority on the target file, so the action is coerced to be
consistent with it:

- `create_new = true` → the only consistent action is `create_new_spec`.
- `create_new = false` → `create_new_spec` is contradictory and is downgraded to a
  safe `append_new_test` into the placement-owned spec.

Implemented in `_reconcile_action_with_placement` in the orchestrator.

#### 3. Confidence gating (safe fallback + review flag)

New settings `min_placement_confidence`, `min_action_confidence`, and
`min_ownership_confidence` (default `0.5`) gate the decisions:

- Below threshold, the only destructive action (`extend_existing_test`, which
  rewrites a proven test block) is downgraded to `append_new_test`. Additive
  actions are kept but flagged.
- Every low-confidence decision adds a reason to `GenerationResult.review_reasons`
  and sets `GenerationResult.needs_review = true`. Generation still completes; the
  result is simply marked for review.

Because deterministic fallbacks carry `confidence = 0.35` (below the default
threshold), any fallback-path decision now flags for review by design. Lower the
relevant threshold if fallback extensions should survive.

#### 4. Real candidate ranking

`CandidateTestRankingAgent` is now an LLM structured-output agent that ranks
existing tests by behavioral overlap with the `FunctionalIntent` (shared route,
screen, journey, assertions, fixtures, page objects), returning a
`CandidateRanking`. It falls back to deterministic passthrough (original order)
when there is no intent, no LLM client, one-or-fewer candidates, or on any error.

#### 5. Flow merge and ownership wired into generation

Both agents moved off the discard-only advisory path onto a resilient
`_run_optional_stage` (returns `None` on failure, never aborts generation) and are
now passed into the code generation prompt:

- The **flow merge plan** tells the generator to keep `stable_region` /
  `preserved_steps` intact and add only `extension_region` / `added_steps`.
- The **ownership resolution** tells the generator to place new locators, helpers,
  and methods in the resolved owner (`owner_path` / `owner_kind`) rather than
  inlining them in the spec.

#### 6. Ownership is a first-class decision

`OwnershipResolution` gained `create_new`, a bounded confidence, and a full
`DecisionTrace`. The prompt now carries reuse-vs-create-page-object standards, the
deterministic fallback reuses an existing owner (never invents one) with a trace,
and low-confidence ownership is flagged for review.

### Flow-reuse grounding (append and extend)

The first hardening pass wired flow-merge and ownership into generation, but the
proven-flow signal was still weak: flow merge was derived from the intent rather
than the real test, appended tests received no sibling flow at all, and nothing
verified that proven steps survived. This pass grounds and verifies flow reuse.

#### Append: anchor flow context

`append_new_test` previously received no existing flow, so a new test could
reinvent a parallel setup. The orchestrator now resolves an **`AnchorFlowContext`**
— the sibling test in the target spec with the richest reusable setup (most page
objects + fixtures) — and passes it into code generation as a reference (never an
edit target), with a rationale recording why it was chosen. The prompt instructs
the generator to reuse the anchor's setup/auth/navigation/fixtures/page objects
and add only the new steps. A deterministic guard (`_append_reuse_check`) then
requires the appended test to reuse at least one of the anchor's page objects or
non-generic fixtures; otherwise it routes to repair rather than shipping a
reinvented flow.

#### Extend: grounded flow merge + preservation guard

`flow_merge.plan(...)` now receives the `ExistingTestContext`, so
`stable_region` / `preserved_steps` come from the actual test source instead of
the intent, and it runs only for `extend_existing_test`. `FlowMergePlan` gained a
bounded confidence and a `DecisionTrace`, and low-confidence merges are flagged
for review. The extension guard now also runs `_dropped_preserved_steps`: any
step the flow plan lists as preserved that actually exists in the original test
source must survive in the replacement, closing the silent step-drop risk.
Paraphrased or invented steps never trigger a false failure because only steps
literally present in the source are enforced.

### Reference integrity and reuse verification

Execution is intentionally out of scope for now; the goal of this pass is that
generated code is high quality on the first write — real locators, real page
object members, real imports — so post-generation edits stay minimal.

#### Locator decisions reach the generator

`LocatorReasoningAgent` (evidence-grounded `LocatorDecisionSet` from source
intelligence) was previously advisory-discarded. It now runs as an optional
stage and its decisions are rendered into the code generation prompt with a hard
rule: use exactly those locators for the matching interactions, never invent
alternatives without source evidence.

#### Reference-integrity guard (deterministic)

A new patch-plan check fails generation (and routes to repair) when generated
code provably references things that don't exist:

- every **relative import** must resolve to a repository file or to another
  patch in the same set;
- every **page-object member call** (`const po = new PlanPage(...)` then
  `po.method()`) must exist in the class source, resolved through the patch's
  own import — an invented `planPage.openDesigner()` no longer survives.

The check is conservative by design: tsconfig-alias imports, inherited classes
(`extends`), and anything unresolvable are skipped, never failed — it only
rejects provably invented references.

#### Ownership grounded in needed locators + emission guard

Ownership resolution now receives the functional intent and source intelligence
(the locators/components the change actually needs), so reuse-vs-create is
decided against the real requirement instead of inventory alone. A deterministic
emission guard then enforces the promise: if ownership says `create_new` for a
page object/helper/fixture, the patch set must contain a patch creating
`owner_path` — locators can no longer be silently inlined into the spec.

#### Create-spec grounding: template anchor + best-practices standard

`create_new_spec` previously generated from repo-wide context only. Now:

- the richest existing test anywhere in the repository is selected as a
  **template anchor** (style/setup reference only — its titles and assertions
  are never copied);
- a **Playwright best-practices scaffold** is injected into the prompt for every
  create: getByRole-first locator priority, web-first assertions, no fixed
  waits, storageState/beforeEach auth, `test.step` structure, parallel-safe
  isolation. When the repository has nothing to reuse (greenfield), this is the
  governing standard; when repo conventions exist, they win;
- a structural guard requires every created spec to import `@playwright/test`
  and contain a `test` block with `expect` assertions.

### Framework bootstrap for repos with no E2E setup

The service has access to the full UI application repository, and the E2E
framework may or may not exist there yet. Previously a repo with no Playwright
at all was hard-rejected (422 unsupported). Bootstrap mode closes that:

- **Classification** — a qualifying UI repo (package.json + Angular/React +
  TypeScript, no competing test framework) with no Playwright config/specs gets
  `requires_bootstrap=true` instead of blockers.
- **Deterministic scaffold** — `BootstrapScaffoldService` emits the framework
  from templates, not the LLM: `playwright.config.ts` (testDir `./e2e`, CI
  retries, trace/screenshot policy, `webServer` derived from the repo's
  start/dev script), a `package.json` merge adding the `@playwright/test`
  devDependency and `test:e2e` script, and an `e2e/fixtures.ts` entry point.
  Only the spec itself is LLM-generated, under the best-practices standard.
- **Placement normalization** — in bootstrap mode the spec placement is steered
  onto the scaffolded `e2e/` convention deterministically.
- **Scaffold guard** — `_bootstrap_scaffold_check` ensures the config and
  dependency patches survive critic review and repair; on collision the
  deterministic scaffold wins over LLM-generated duplicates.

### Prompt hardening (contract quality and context discipline)

The Pydantic layer guarantees bad output cannot ship; prompt hardening reduces
how often the repair loop and low-confidence fallbacks fire in the first place:

- **Real examples for every structured model.** `CandidateRanking`,
  `OwnershipResolution`, `FlowMergePlan`, `LocatorDecisionSet`, and
  `SourceIntelligence` previously fell through to a generic fallback that showed
  an empty object as the "valid example" — actively teaching the model to fail
  validation. Each now has a canonical valid/invalid pair, and unknown models get
  schema-only guidance instead of a fabricated example.
- **Action-labeled PatchSet few-shots.** The patch contract now shows all three
  shapes the guards accept: `create_new_spec`, `append_new_test` (anchor-reusing
  append), and `extend_existing_test` (exact-range replace preserving the title
  and proven steps).
- **Context curation.** Prompts no longer dump raw payloads: repository
  inventory is stripped of per-file hashes and capped (E2E candidates kept
  first), every UI-context evidence list is capped, and candidate tests are
  capped to the top 25 with truncated excerpts. The extend target's
  `ExistingTestContext` excerpt is deliberately never truncated — it is the
  replace source.
- **DecisionTrace quality floor.** A placement/action trace with no decision,
  justification, or evidence validates structurally but is unreviewable; it now
  adds a `review_reasons` entry (non-blocking).

### Old vs new at a glance

```text
Concern                     Old                         New
--------------------------  --------------------------  ----------------------------
Action type                 bare string                 Literal enum -> fallback
Confidence                  logged, unused              gated -> safe fallback + flag
Placement vs action         unchecked                   reconciled deterministically
Candidate ranking           no-op passthrough           LLM overlap ranking
Flow merge / ownership      advisory, discarded         wired into code generation
Ownership decision          owner path only             create_new + DecisionTrace
Review signal               none                        needs_review + review_reasons
Flow merge source           functional intent           grounded in existing test
Append flow reuse           none (reinvented)           anchor context + reuse guard
Extend step preservation    prompt-only                 deterministic guard
Locator decisions           advisory, discarded         fed into code generation
Invented references         undetected                  reference-integrity guard
Ownership inputs            inventory only              intent + source evidence
Owner creation promise      unenforced                  emission guard
Create-spec grounding       repo-wide context only      template anchor + best practices
No-framework repos          rejected (422)              bootstrap scaffold + guard
Schema examples             4 models, {} fallback       all models, no fabricated example
Prompt payloads             raw dumps (incl. hashes)    curated + capped context
Trace quality               structural only             shallow traces flagged
```

### Where these live

```text
app/schemas/test_action_decision.py     Literal action + TestActions constants
app/schemas/spec_placement.py           bounded confidence + labels
app/schemas/candidate_ranking.py        ranking schema (new)
app/schemas/behavioral_test_unit.py     ExistingTestContext + AnchorFlowContext
app/schemas/flow_merge.py               confidence + DecisionTrace
app/schemas/ownership_resolution.py     create_new + DecisionTrace
app/schemas/generation_result.py        needs_review + review_reasons
app/prompts/candidate_ranking_prompt.py ranking prompt (new)
app/prompts/flow_merge_prompt.py        grounded in existing test source
app/prompts/code_generation_prompt.py   anchor/flow/ownership/locator reuse rules
app/prompts/prompt_sections.py          best-practices scaffold, per-model
                                        examples, context curation helpers
app/prompts/ownership_resolution_prompt.py  needed-locators grounding
app/agents/candidate_test_ranking_agent.py  real LLM ranking + fallback
app/services/generation_orchestrator.py reconcile, gates, optional stages,
                                        anchor flow, bootstrap wiring,
                                        patch-plan guards (extension, append
                                        reuse, reference integrity, ownership
                                        emission, created-spec structure,
                                        bootstrap scaffold)
app/services/repo_strategy_service.py   bootstrap classification
app/services/bootstrap_scaffold_service.py  deterministic framework scaffold (new)
app/schemas/repo_profile.py             requires_bootstrap flag
app/config.py                           min_*_confidence thresholds
```

## Architecture

### API Layer

Located in:

```text
app/api/routes/
```

Responsibilities:

- Accept generation requests.
- Return generation results.
- Expose job status.
- Expose SSE event stream.

The route layer is intentionally thin. It delegates workflow execution to the
orchestrator.

### Orchestrator Layer

Located in:

```text
app/services/generation_orchestrator.py
```

Responsibilities:

- Coordinate the full generation lifecycle.
- Call repository profiling, intelligence, inventory, agent, patching, and
  validation services in order.
- Centralize job-level exception logging.
- Return the final `GenerationResult`.

The orchestrator should not contain deep business logic. Stage-specific logic
belongs in agents, services, tools, patching, or validation modules.

### Service Layer

Located in:

```text
app/services/
```

Responsibilities:

- Repository profiling.
- Technology detection.
- Test classification.
- Inventory construction.
- Source intelligence coordination.
- Behavioral inventory extraction.
- Spec placement coordination.
- Test action decision coordination.
- Flow merge coordination.
- Ownership resolution coordination.
- Code generation coordination.
- Final result building.

Services are the bridge between deterministic tools and agent decisions.

### Agent Layer

Located in:

```text
app/agents/
```

Responsibilities:

- Convert functional requirements into structured intent.
- Map intent to source evidence.
- Decide target spec placement.
- Rank candidate tests.
- Decide extend vs append vs create.
- Preserve stable execution flow.
- Decide artifact ownership.
- Justify locators from source evidence.
- Generate structured patches.
- Repair generated changes after validation failure.

Every agent inherits from:

```text
app/agents/base_agent.py
```

The base class centralizes common logging behavior and the structured LLM call
shape. Agents should never import OpenAI, Anthropic, Bedrock, Gemini, or other
provider SDKs directly.

### Tool Layer

Located in:

```text
app/tools/
```

Responsibilities:

- Read files safely.
- Write files with backups.
- Search via ripgrep.
- Query Git state and diff.
- Parse TypeScript, Angular, and Playwright structures.
- Run validation commands.

Tools are deterministic. They do not make semantic decisions.

### Inventory Layer

Located in:

```text
app/inventory/
```

Responsibilities:

- Build repository inventory from Git, file fingerprints, specs, page objects,
  fixtures, and helpers.
- Cache inventory by repository state.
- Provide query helpers for downstream stages.
- Track file-level relationships.

The design intentionally avoids embeddings, vector databases, and RAG. The
inventory is deterministic and based on Git, ASTs, file paths, and file hashes.

### Patching Layer

Located in:

```text
app/patching/
```

Responsibilities:

- Validate patch intent.
- Backup files before write.
- Apply scoped patches only.
- Generate readable diffs.

The patching layer is responsible for safe repository mutation. Agents generate
structured patch intent; they do not overwrite arbitrary files.

### Validation Layer

Located in:

```text
app/validation/
```

Responsibilities:

- Syntax/type-level checks.
- Playwright test discovery.
- Duplicate test title detection.
- Repo command execution for lint, typecheck, and test commands.

The current validators are placeholders. The next implementation phase should
wire real package-manager commands and parser-based duplicate test checks.

## LLM Adapter Design

Agents must use the existing model abstraction instead of provider SDKs.

Preferred shape:

```python
self.llm = ModelClientFactory.get_client(
    provider_name,
    model_config,
    model_params,
    db,
    tenant_id,
)
```

Or, if using the existing wrapper:

```python
self.llm = DefaultLLMClient(
    db=db,
    tenant_id=tenant_id,
)
```

Agent usage:

```python
decision = self.llm.complete_structured(
    prompt=prompt,
    response_model=SpecPlacementDecision,
)
```

Current implementation files:

```text
app/llm/llm_client.py
app/llm/default_llm_client.py
app/llm/llm_client_factory.py
app/runtime/generation_runtime.py
app/prompts/
```

`GenerationRuntime` is created per request and carries the job, tenant,
repository, branch, database handle, and LLM client. `LLMClientFactory` creates
a `DefaultLLMClientAdapter` from the existing Worktop model stack.

Because this is an agentic generation process, missing model configuration is a
hard failure. If `tenant_id` is absent or the real client cannot be created, the
request fails before any agent decision is made. This avoids silently generating
repository changes from placeholder logic.

The following agents now call `complete_structured(...)` through `BaseAgent`
when an LLM client is available:

- Functional intent.
- Source mapping.
- Spec placement.
- Test action decision.
- Flow merge.
- Ownership resolution.
- Locator reasoning.
- Code generation.
- Repair.
- Critic review.

This preserves:

- Provider independence.
- Tenant-based model configuration.
- Existing retry behavior.
- Existing telemetry.
- Existing logging.
- Existing DAO and configuration patterns.

## Logging Design

The scaffold reuses the existing custom logger package:

```python
from worktop.core_services.app.utility.custom_logger.log_helpers import (
    log_card_simple,
    log_exception,
    log_metric,
    log_step,
)

from worktop.core_services.app.utility.custom_logger.logging import (
    log_performance,
    logger,
)
```

It does not create a new logger.

Shared logging metadata is normalized by:

```text
app/utils/logging_utils.py
```

Supported metadata keys:

```text
job_id
tenant_id
repo_path
branch
stage
agent_name
```

Standard patterns:

```python
log_step("repo_strategy_started", {"repo_path": repo_path})
log_metric("candidate_tests_count", len(candidate_tests))
logger.info("Generation job completed successfully")
```

Exception pattern:

```python
try:
    ...
except Exception as exc:
    log_exception(exc, context={"job_id": job_id, "stage": "spec_placement"})
    raise
```

Performance pattern:

```python
@log_performance("repo_strategy_service.detect")
def detect(...):
    ...
```

## Decision Contract

Every agent decision should follow this structure:

```json
{
  "decision": "extend_existing_test",
  "confidence": 0.91,
  "justification": "Existing test owns the same business flow; new case adds only post-save validations.",
  "evidence": [
    "Same business capability",
    "Same page object",
    "Same auth fixture",
    "82% execution flow overlap"
  ],
  "alternatives": [
    {
      "decision": "append_new_test",
      "reason_rejected": "Would duplicate existing save flow"
    }
  ],
  "risk": "Low",
  "fallback": "Create new test if validation fails"
}
```

This is represented by:

```text
app/schemas/decision_trace.py
```

## Write Rules

The generator must follow these write rules:

- Extend existing test: replace the matched test block in the same position.
- Append new test: insert at the end of the matching `describe` block.
- Create new spec: create using detected repository convention.
- New locator or functionality: add to owning page object, helper, or fixture
  when that convention exists.
- Always create a backup before writing.
- Always return files changed and diff summary.

## Guardrails

The design explicitly rejects:

- Keyword-only matching.
- Nearest Jira ID matching.
- Vector DB lookup.
- Embedding-based retrieval.
- RAG flow for source selection.
- Raw locators in specs when a page object exists.
- Random line insertion.
- Whole-spec rewrite for extension.
- Unit or integration spec modification for E2E generation.
- Locator generation without source evidence.
- Writes without backup.
- Duplicate test names.
- Repair outside approved generated scope.
- Out-of-vocabulary decision actions (enforced by `Literal` typing).
- Placement and test action that disagree (reconciled deterministically).
- Destructive `extend_existing_test` edits under low confidence (downgraded to
  `append_new_test` and flagged for review).
- Invented page-object members and unresolvable relative imports (reference-
  integrity guard).
- Promised new owners (page object/helper/fixture) that the patch set does not
  actually create (ownership-emission guard).
- Created spec files without Playwright structure (`@playwright/test` import,
  `test` block, `expect` assertions).

## Repository Truth Model

The system uses five sources of truth:

```text
Functional case        = intent
Feature branch source  = execution truth
Existing Playwright    = coverage truth
Repo conventions       = architecture truth
Validation             = executable truth
```

## Current Beta Limitations

This repository currently contains a professional scaffold, not the final
production generator. The following areas are intentionally staged for the next
implementation pass:

- Production DB/session injection for the existing Worktop model stack.
- Tenant/model configuration resolution beyond the request-level `tenant_id`.
- Production-grade prompt tuning and test fixtures for each agent.
- Deeper repo support rules for custom app ownership, nested package managers,
  and organization-specific test conventions.
- TypeScript AST parser implementation.
- More precise Playwright parsing through TypeScript AST support for highly
  custom wrappers and multiline edge cases.
- Angular source parser implementation.
- Functional case reconciliation against branch source.
- Inventory cache invalidation by Git HEAD and file hash.
- Package-manager lint, typecheck, and targeted Playwright command execution.
- Durable job store and SSE event publisher.
- Repair loop with retry budget and generated-scope enforcement.
- Adapters for Cypress, Selenium, non-TypeScript Playwright, complex monorepos,
  custom test DSLs, and infrastructure-heavy validation environments.

## Local Development

Install dependencies in your preferred Python environment:

```bash
pip install -e .
```

Run the service:

```bash
uvicorn app.main:app --reload
```

Run a sample request:

```bash
curl -X POST http://localhost:8000/api/playwright/generate \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "demo",
    "repo_path": "/path/to/repo",
    "branch": "main",
    "test_case_name": "Create order",
    "steps": ["Open orders", "Create order", "Verify status"],
    "run_validation": true
  }'
```

Compile check:

```bash
python3 -m compileall -q test-agent
```

## File Map

```text
app/main.py
app/config.py
app/api/routes/
app/schemas/
app/services/
app/agents/
app/tools/
app/inventory/
app/patching/
app/validation/
app/utils/
```

The architecture is intentionally modular so each workflow stage can be
implemented and tested independently while preserving one consistent generation
contract.
