# API Agent Service

`api-agent` is the backend home for repository-native API Test Generation.

It is designed for developers working on active sprint API tickets. The service
must inspect each team's repository and generate API tests that match the
team's existing language, framework, folder structure, fixtures, mocks, auth
helpers, naming conventions, CI commands, and stage validation style.

The frozen design is documented in:

```text
IMPLEMENTATION_PLAN.md
```

## Product Principle

Do not generate generic API tests.

Generate tests from repository evidence:

```text
story context
repo structure
API endpoints and schemas
existing API tests
team test strategy
fixtures and helpers
mock/auth/client patterns
CI/stage commands
```

## Initial Supported Repo Families

```text
Java
  Spring Boot + JUnit 5 + RestAssured
  Spring Boot + JUnit 5 + MockMvc
  Maven / Gradle
  Mockito / WireMock

Python
  FastAPI / Flask / Django-style APIs
  pytest
  requests / httpx / framework TestClient
  responses / respx / pytest-mock
```

## Backend Flow

```text
route
  -> task manager
  -> orchestrator
  -> repo context
  -> team test strategy discovery
  -> strategy registry
  -> scenario/code generation agents
  -> file writer
  -> validation
  -> status/events
```

## Current API Scaffold

```text
POST /api/api-test-generation/generate-api-scenarios
POST /api/api-test-generation/generate-api-test-code
POST /api/api-test-generation/generateApiTests
GET  /api/api-test-generation/jobs/{task_id}
GET  /api/api-test-generation/events/{task_id}
POST /api/api-test-generation/abort/{task_id}
POST /api/api-test-generation/checkRepoProfile
POST /api/api-test-generation/generateRepoProfile
```

## Current Status

Backend scaffold exists.

Portable UI scaffold exists under:

```text
frontend/test-generation/
```

It is not wired into the real Worktop Test Generation page yet because that
host page is not present in this repository snapshot.

## Generation Hardening

The backend follows the same hardening standards as `test-agent` (see that
repo's "Decision Intelligence Hardening" section): typed contracts and
deterministic guards around every LLM output, plus a review signal on results.

### Typed contracts

- `ApiScenario.scenario_type` / `priority` / `method` and
  `GeneratedTestFileOutput.test_target` are `Literal` types — out-of-vocabulary
  model output fails validation and routes to the repair/fallback path instead
  of flowing downstream. `GeneratedFile.operation` is `created|updated`.
- Both results (`ApiScenarioGenerationResult`, `ApiTestGenerationResult`) carry
  `needs_review` + `review_reasons` populated by the guards.

### LLM adapter robustness

`WorktopModelClientAdapter.complete_structured` extracts JSON from fenced or
prose-wrapped responses and performs one repair retry (re-prompting with the
Pydantic validation error and schema) before raising to the deterministic
fallbacks.

### Schema-derived prompt contracts

Prompts no longer hand-write the JSON shape (which could drift from the
schemas): `response_contract()` in `app/prompts/prompt_sections.py` renders the
Pydantic JSON schema plus canonical valid/invalid examples for
`ScenarioPlanOutput` and `TestCodeOutput`.

### Scenario plan guard

Deterministic post-generation checks: duplicate scenario ids and scenarios with
no steps or no assertions are dropped with warnings; scenarios targeting an
endpoint that matches nothing detected in the repository still ship but are
flagged in `review_reasons`.

### Generated-file write guard (safety critical)

The LLM controls `relative_path`, so before writing, `GeneratedFileGuard`
enforces: the path must be provably a test file (detected team test locations
or per-language test naming — `src/test/`, `*Test.java`, `test_*.py`, …); it
must never land on application source; content must be non-empty with a
test-framework signal and at least one assertion; `test_target` must match the
requested execution target. Rejected files are dropped with review reasons, and
if nothing survives, deterministic strategy skeleton files are written instead
of unsafe model output.

### Agentic core (repo-agnostic, Codex/Claude Code style)

- **Model-directed discovery loop.** `RepoDiscoveryAgent` explores the
  repository itself: each turn it requests `read_file` / `search` / `list_dir`
  (bounded and sandboxed), reads the results, and repeats until it emits an
  evidence-grounded `RepoUnderstanding` (languages, test frameworks, locations,
  CI/stage commands, conventions, example tests — any stack, nothing
  hardcoded). The understanding outranks the scanner profile and the strategy
  registry, which is demoted to a hint.
- **Convention-derived guards.** Test-likeness in the write guard comes from
  the repo's own detected test locations and existing test directories first;
  per-language heuristics are only the last-resort universal check.
- **Scaffolds never masquerade as coverage.** Deterministic fallback scenarios
  and skeleton files are explicitly marked `SCAFFOLD`, and any scaffold output
  forces `needs_review` with a "not real coverage" review reason.
- **Guard-repair self-healing.** When the write guard rejects generated
  files, the findings are fed back to the model and it regenerates (bounded by
  `max_generation_repair_attempts`); scaffold skeletons are only the very last
  resort after healing fails.
- **Env-gated execution feedback loop.** With `enable_test_execution=true`, the
  resolved repo test command actually runs; on failure the output is fed back
  to the model for a bounded repair round (regenerate → guard → rewrite →
  re-run). Off by default so environments without repo dependencies still work.

## Implementation Phases

### Phase 1: Backend Strategy Foundation

Status: started.

Scope:

```text
Expand repo/team strategy profile
Detect Java/Python stacks
Detect API test frameworks and folder structures
Add strategy registry
Route generation through Java/Python strategies
```

### Phase 2: Backend Generation Quality

Status: started.

Scope:

```text
Reuse existing API tests as examples
Reuse existing fixture/auth/client helpers
Read controller/route/service source context
Detect dependencies from controller/route files
Plan mocks, stubs, and dependency overrides
Resolve repo-native validation commands
Generate CI and stage variants differently
Publish strategy, confidence, warnings, reused examples, mock/stub plan, and validation summary
```

### Phase 3: UI

Status: scaffold generated, host wiring pending.

Scope:

```text
Add API Test Generation tab inside existing Test Generation
Show story context, detected API impact, scenarios, progress, abort, files, and validation
```

### Phase 4: Worktop Integration

Status: not implemented.

Scope:

```text
Wrap routes with API envelope and JWT permissions
Reuse DB session and existing DAOs
Reuse shared story/API setup steps
Reuse Worktop local workspace path resolution
```

## Runtime

The LLM integration is adapter-based. `app/llm/model_client_factory.py` creates
an `LLMClient` through `WorktopModelClientAdapter`, which first tries the
existing Worktop `DefaultLLMClient` path. That path is expected to resolve model
configuration through the existing model configuration DAO and
`ModelClientFactory`.

The local fallback client exists only so this service can be imported and smoke
tested outside the full Worktop runtime.

## Development

```bash
cd api-agent
python -m compileall -q app
uvicorn worktop.api_agent.app.main:app --reload --port 8091
```
# Documentation

- [`FUNCTIONAL_GUIDE.md`](FUNCTIONAL_GUIDE.md) — story-to-scenario and scenario-to-code behavior.
- [`TECHNICAL_ARCHITECTURE.md`](TECHNICAL_ARCHITECTURE.md) — backend/frontend architecture, mocks and wiring.
