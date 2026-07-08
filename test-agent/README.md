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

Beta does not target Cypress/Selenium repos, non-TypeScript Playwright repos,
highly custom test DSLs, complex build-system monorepos, or repositories
requiring remote infrastructure/secrets for basic validation.
```

### Runtime Scope Enforcement

`RepoStrategyService` classifies every request before the LLM runtime is created.
The generated `RepoProfile` includes:

- `support_status`: `supported`, `supported_with_warnings`, or `unsupported`.
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
Flow Stability / Flow Merge Agent
   ↓
Ownership Resolution Agent
   ↓
Locator and Functionality Justification Agent
   ↓
Code Generation Agent
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
`app/services/generation_orchestrator.py`. Some stages are implemented as
deterministic placeholders so the system shape is stable before connecting the
real LLM adapter and parser implementations.

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
