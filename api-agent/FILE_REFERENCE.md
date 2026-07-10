# API Agent File Reference

This is a navigation/reference guide for the API Test Generation work. It
describes what each backend area does today and what frontend files should do
when UI work starts.

## Root Files

### `README.md`

High-level product and runtime overview. It explains that `api-agent` is for
repository-native API test generation, lists the initial Java/Python repo
families, and separates Phase 1, Phase 2, Phase 3, and Phase 4.

### `IMPLEMENTATION_PLAN.md`

Frozen design document. This is the source of truth for scope, sequencing, team
test strategy profile, supported stacks, task lifecycle, UI direction, and
backend-first acceptance criteria.

### `pyproject.toml`

Python project metadata and dependency declaration for the standalone
`api-agent` service. It declares FastAPI, Pydantic, settings, and uvicorn.

## Backend App Entry

### `app/main.py`

FastAPI application bootstrap. Registers route modules for scenario generation,
test generation, job status, SSE events, and repo profile endpoints. Also maps
API-agent exceptions to JSON responses.

### `app/config.py`

Small settings object for service name, event buffer size, and worker count.

### `app/errors.py`

Shared exception types such as task-not-found, abort-requested, and unsafe
workspace path errors.

## API Routes

### `app/api/routes/api_scenario_routes.py`

Endpoint for scenario generation:

```text
POST /api/api-test-generation/generate-api-scenarios
```

It stays thin and delegates to the task manager.

### `app/api/routes/api_test_generation_routes.py`

Endpoints for API test generation:

```text
POST /api/api-test-generation/generate-api-test-code
POST /api/api-test-generation/generateApiTests
```

The second endpoint mirrors the ScriptGen-style request shape.

### `app/api/routes/job_routes.py`

Task status and abort endpoints. Supports both task-id and stable key based
lookup/abort.

### `app/api/routes/event_routes.py`

SSE streaming endpoints for generation status updates.

### `app/api/routes/repo_profile_routes.py`

Repo profile check/generation endpoints:

```text
POST /api/api-test-generation/checkRepoProfile
POST /api/api-test-generation/generateRepoProfile
```

These generate `api_repo_profile.json` from repository evidence.

## Schemas

### `app/schemas/repo_profile.py`

Core repository intelligence schema. Contains endpoint candidates, existing API
test candidates, and the expanded `TeamTestStrategyProfile`.

### `app/schemas/team_test_strategy.py`

Compatibility export for `TeamTestStrategyProfile`.

### `app/schemas/api_scenario.py`

API scenario row model used by the scenario table and generation flow.

### `app/schemas/api_scenario_request.py`

Request model for generating API scenarios from a story and repository context.

### `app/schemas/api_scenario_result.py`

Response model for generated API scenarios, repo findings, and warnings.

### `app/schemas/api_test_generation_request.py`

Request models for generating tests:

```text
GenerateApiTestCodeRequest
GenerateApiTestsRequest
```

`GenerateApiTestsRequest` is the ScriptGen-style wrapper that can convert into
the lower-level code-generation request.

### `app/schemas/api_test_generation_result.py`

Result model for generated files, validation, selected strategy, reused
examples, source snippets, and mock/stub plan.

### `app/schemas/source_context.py`

Phase 2 context models:

```text
SourceSnippet
ExistingTestExample
DependencyCandidate
GenerationSourceContext
```

These carry existing test examples, endpoint source snippets, fixture snippets,
and dependencies into generation.

### `app/schemas/mock_stub_plan.py`

Mock/stub plan returned in generation results. Captures selected mock strategy,
helpers to reuse, dependencies to mock, generated stub intentions, and warnings.

### `app/schemas/llm_outputs.py`

Structured LLM output models for scenario planning and test-code generation.

### `app/schemas/repo_understanding.py`

`DiscoveryRequest`, `DiscoveryTurn`, and `RepoUnderstanding` — the discovery
loop protocol and its evidence-grounded conclusion (any language/stack).

### `app/schemas/generated_file.py`

Generated file summary: path, operation, test target, and summary.

### `app/schemas/validation_result.py`

Validation result model with pass/fail, command, summary, and details.

### `app/schemas/event.py`

SSE event payload model.

### `app/schemas/generation_job.py`

Task/job model containing status, payload, result, error, events, and abort
state.

### `app/schemas/execution_target.py`

Enum for CI, stage, and both.

### `app/schemas/task_status.py`

Enum for queued/running/aborting/aborted/completed/failed.

### `app/schemas/queued_task.py`

Immediate queue response containing `queued` and `task_id`.

## Runtime And LLM

### `app/runtime/generation_runtime.py`

Per-task runtime object. Creates the model client through the LLM factory.

### `app/llm/llm_client.py`

Protocol/interface for complete and structured completion calls.

### `app/llm/model_client_factory.py`

Factory that creates an `LLMClient`. It prefers the Worktop model adapter and
falls back only for local scaffold use.

### `app/llm/worktop_model_client_adapter.py`

Adapter around Worktop model infrastructure. It tries `DefaultLLMClient` first,
then the lower-level `ModelClientFactory` path. `complete_structured` extracts
JSON from fenced/prose-wrapped responses and performs one repair retry with the
Pydantic validation error before raising.

### `app/llm/local_fallback_client.py`

Local-only fallback so the scaffold can be imported in environments without the
full Worktop model runtime.

## Agents And Prompts

### `app/agents/repo_discovery_agent.py`

Model-directed repository discovery (Codex/Claude Code style): a bounded
read_file/search/list_dir tool loop that concludes with an evidence-grounded
`RepoUnderstanding`. Failure never blocks generation.

### `app/agents/base_agent.py`

Common logging and structured completion behavior for agents.

### `app/agents/scenario_agent.py`

Generates API scenarios. Falls back to deterministic scenarios when model
output is unavailable.

### `app/agents/test_generation_agent.py`

Generates API test code. Selects a strategy from the registry, builds a prompt
with source context/mock plan, and uses strategy-specific fallback files if
model output is unavailable.

### `app/prompts/api_scenario_prompt.py`

Prompt builder for scenario generation.

### `app/prompts/api_test_code_prompt.py`

Prompt builder for API test generation. Includes repo profile, strategy
guidance, existing tests, source snippets, fixtures, and mock/stub plan.

### `app/prompts/prompt_sections.py`

Reusable renderers for repo profile, source context, and mock/stub plan, plus
`response_contract()` — the schema-derived response contract with canonical
valid/invalid examples for `ScenarioPlanOutput` and `TestCodeOutput`, so
prompts can never drift from the Pydantic schemas.

## Services

### `app/services/generation_orchestrator.py`

Main workflow coordinator. Handles repo scan, source context extraction,
mock/stub planning, LLM runtime creation, generation, file writing, validation,
progress publishing, and abort checks.

### `app/services/api_repo_context_service.py`

Builds `RepoProfile` by scanning repository structure, endpoints, existing
tests, and team strategy.

### `app/services/team_test_strategy_service.py`

Discovers the team test strategy profile. Detects language, frameworks, test
frameworks, mocks, auth helpers, fixtures, commands, example tests, and
confidence/warnings.

### `app/services/source_context_service.py`

Builds `GenerationSourceContext` by selecting endpoint source snippets, closest
existing test examples, and fixture/auth/client snippets.

### `app/services/mock_stub_planning_service.py`

Creates `MockStubPlan` from endpoint dependencies, existing mock frameworks,
helpers, and outbound service signals.

### `app/services/api_scenario_generation_service.py`

Service around `ScenarioAgent` with a deterministic scenario guard: drops
duplicate ids and scenarios without steps/assertions, flags scenarios targeting
undetected endpoints into `review_reasons`, and sets `needs_review`.

### `app/services/api_test_code_generation_service.py`

Runs `TestGenerationAgent`, passes the output through `GeneratedFileGuard`
before writing, falls back to deterministic strategy skeleton files when the
guard rejects everything, validates, and builds the final result with
`needs_review` / `review_reasons`.

### `app/services/api_test_file_writer.py`

Writes generated files safely into the local repository.

### `app/services/api_repo_profile_service.py`

Checks and generates `api_repo_profile.json`.

## Strategies

### `app/strategies/base_strategy.py`

Strategy interface and `StrategyMatch` metadata. All generation strategies must
implement support checks, matching, fallback files, and validation command
resolution.

### `app/strategies/strategy_registry.py`

Selects the best generation strategy based on the repo profile. Current
strategies cover Java/Spring and Python/pytest families.

### `app/strategies/java_spring_mockmvc_strategy.py`

Java Spring Boot MockMvc strategy for controller/API-slice CI tests. Fallback
output includes detected helpers and Mockito/WireMock guidance.

### `app/strategies/java_spring_rest_assured_strategy.py`

Java RestAssured strategy for integration/stage style API tests. Fallback output
includes request-spec/auth-helper guidance.

### `app/strategies/python_fastapi_testclient_strategy.py`

Python FastAPI/framework TestClient strategy. Fallback output includes fixture,
auth-helper, dependency override, and respx/responses/pytest-mock guidance.

### `app/strategies/python_pytest_httpx_strategy.py`

Python pytest HTTP-client strategy for requests/httpx based API tests.

## Tools

### `app/tools/path_safety.py`

Workspace path resolution and safe path join helpers.

### `app/tools/file_reader_tool.py`

Safe repository file listing and bounded text reads.

### `app/tools/file_writer_tool.py`

Safe file writing into the repo and generated file summary creation.

### `app/tools/search_tool.py`

Simple text search over repository files.

### `app/tools/api_endpoint_scanner_tool.py`

Detects API endpoint candidates from Java/Spring, Python/route-like, and common
HTTP method signals.

### `app/tools/existing_test_scanner_tool.py`

Finds existing API tests and detects framework, target, strategy, and signals.

### `app/tools/fixture_scanner_tool.py`

Finds fixture files, auth helpers, API client helpers, test data builders, and
base test classes.

### `app/tools/source_context_tool.py`

Selects closest endpoint source files, existing test examples, and fixture
snippets for generation.

### `app/tools/dependency_scanner_tool.py`

Detects Java controller/service dependencies and Python route/outbound-client
dependencies that may require mocks, stubs, or overrides.

### `app/tools/mock_stub_scanner_tool.py`

Detects preferred mock/stub strategy from repo evidence.

### `app/tools/command_discovery_tool.py`

Discovers likely CI/stage commands from Maven, Gradle, package.json, pytest, and
test folders.

### `app/tools/openapi_scanner_tool.py`

Finds OpenAPI/Swagger and GraphQL schema files.

### `app/tools/git_tool.py`

Small Git helper for current branch and changed files.

## Validation

### `app/validation/api_test_validator.py`

Validates generated files exist and delegates command resolution; passes the
env-gated `execute` flag through to real command execution.

### `app/validation/generated_file_guard.py`

Deterministic pre-write review of LLM-generated files: path must be provably a
test file (detected team test locations or per-language test naming), never
application source; content must carry a test-framework signal and assertions;
`test_target` must match the requested execution target. Rejected files are
dropped with review reasons.

### `app/validation/validation_command_resolver.py`

Resolves the best repo-native validation command for CI or stage.

### `app/validation/repo_command_validator.py`

Dry-run validator that reports the command it would run. Real command execution
is intentionally not enabled yet.

## Task Managers

### `app/task_managers/api_test_generation_task_manager.py`

ScriptGen-style background execution manager. Owns queueing, worker pool,
status, stable keys, abort flags, and job state.

### `app/task_managers/api_test_generation_sse_manager.py`

Buffered SSE event manager for progress streaming.

## Utilities

### `app/utils/logging_utils.py`

Adapter around Worktop custom logging. Provides local logging fallback when
Worktop logging imports are unavailable.

## Tests

### `tests/README.md`

Backend test plan. Lists the unit/integration tests needed before UI
integration.

### `tests/test_generation_hardening.py`

Unit tests for the hardening layer: Literal contract validation, adapter fence
extraction and repair retry, schema-derived prompt contracts, the scenario
guard, the generated-file write guard, and the service-level fallback when all
generated files are rejected.

## Frontend Files

The portable frontend scaffold lives under:

```text
api-agent/frontend/test-generation/
```

It is not wired into the real Worktop Test Generation page yet because that
host frontend module is not present in this repository snapshot.

### `frontend/test-generation/test-generation.component.ts`

Parent Test Generation component. Should only own tab state and shared story
selection wiring.

### `frontend/test-generation/test-generation.component.html`

Parent shell that renders Functional Test Generation and API Test Generation
tabs.

### `frontend/test-generation/test-generation.component.scss`

Styles the parent tab shell, page header, and tab strip.

### `frontend/test-generation/functional-test-gen/*`

Existing or future functional generation feature area. API work should avoid
mixing API-specific state into these files.

### `frontend/test-generation/functional-test-gen/functional-test-gen.component.ts`

Placeholder standalone component for the existing functional generation
experience. The real host app should replace this with its current functional
test generation component.

### `frontend/test-generation/functional-test-gen/functional-test-gen.component.html`

Placeholder template for the functional tab.

### `frontend/test-generation/functional-test-gen/functional-test-gen.component.scss`

Placeholder styling for the functional tab.

### `frontend/test-generation/api-test-gen/api-test-gen.component.ts`

API tab state owner. Should load stories, selected story context, scenario
rows, selected scenarios, current job, progress events, generated files, and
validation summary.

### `frontend/test-generation/api-test-gen/api-test-gen.component.html`

API tab layout:

```text
Sprint API Stories
Selected story context
Detected API impact
API scenario table
Generate CI / Stage / Selected actions
Progress panel with Abort
Generated file summary
Validation summary
```

### `frontend/test-generation/api-test-gen/api-test-gen.component.scss`

Quiet enterprise styling for dense tables, compact status panels, and generated
file summaries.

### `frontend/test-generation/services/api-test-generation.service.ts`

Angular service for API calls:

```text
generateApiScenarios
generateApiTests
getJob
streamEvents
abort
checkRepoProfile
generateRepoProfile
```

### `frontend/test-generation/models/api-scenario.model.ts`

Frontend model matching `ApiScenario`.

### `frontend/test-generation/models/api-test-generation.model.ts`

Frontend models for queue responses, job status, generated files, validation,
source examples, and mock/stub plan.
