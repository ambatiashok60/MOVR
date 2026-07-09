# API Test Generation Frozen Design

## Scope

The product scope is **repository-native API test generation for real developer
adoption across sprint API tickets**.

The goal is not to generate generic API test files. The goal is to understand a
team's repository, testing strategy, folder structure, fixtures, mocks, auth
helpers, naming conventions, and validation commands, then generate tests that
look like the team wrote them.

This design is frozen for the next implementation pass:

```text
Backend intelligence first.
UI second.
Worktop controller integration third.
```

## Current Status

`api-agent` currently contains the backend scaffold only.

Implemented:

- FastAPI route shell for API scenario generation and API test generation.
- ScriptGen-style background task manager with queue, worker pool, status, SSE,
  task keys, and abort support.
- Adapter-based LLM client layer that routes through Worktop's existing
  `DefaultLLMClient` / `ModelClientFactory` path when available.
- Repository scanner for basic API endpoint and existing test discovery.
- API scenario agent and API test generation agent.
- Repo profile check/generation endpoints.
- Basic generated file writer and validation placeholder.

Not implemented yet:

- Integration into the existing Worktop Test Generation page.
- Team test strategy discovery.
- Java/Python strategy-specific generators.
- Strong repo profile intelligence for testing frameworks, auth, fixtures,
  mocks, contract tests, CI commands, and stage commands.
- Real compile/test command execution.
- Review/diff UI.

## Non-Negotiable Product Principle

Every generated test must be based on repository evidence.

The agent should inspect and reuse:

```text
existing test folders
existing test naming conventions
existing fixture files
existing auth helpers
existing API clients
existing mocks/stubs
existing base classes
existing validation commands
existing CI/stage split
existing example tests
```

If the agent cannot infer a convention with enough confidence, it must report a
warning and generate a conservative skeleton in a clearly isolated generated
folder. It should not silently invent a team convention.

## Developer Workflow

Visible flow:

```text
Story -> API impact -> suggested scenarios -> CI/stage target -> generate -> progress -> files/validation
```

Developer mental model:

```text
I changed or added an API for this sprint ticket.
Find the impacted API surface.
Suggest the useful API test scenarios.
Classify what belongs in CI, stage, or both.
Generate tests that match this repo's language, framework, fixtures, and style.
Write the files into my local workspace.
Validate enough that I trust the result.
```

Internal flow:

```text
Story context
Repository scan
Team test strategy discovery
Stack detection
Endpoint/schema discovery
Existing test convention extraction
Scenario planning
CI/stage classification
Strategy-specific code generation
File write
Validation
Status/events
```

## Supported Team Reality

The initial users have both Java-based and Python-based API repositories.

Initial supported stacks:

```text
Java
  Spring Boot + JUnit 5 + RestAssured
  Spring Boot + JUnit 5 + MockMvc
  Spring Boot + Mockito/WireMock for CI-safe dependency isolation
  Maven and Gradle

Python
  FastAPI / Flask / Django-style services
  pytest
  requests / httpx / framework TestClient patterns
  responses / respx / pytest-mock for CI-safe dependency isolation
  pyproject.toml / pytest.ini / setup.cfg based test configuration
```

Future stacks:

```text
Node.js + Jest/Supertest
.NET + xUnit/WebApplicationFactory
Go + testing/httptest
OpenAPI contract-only repositories
GraphQL API repositories
```

## Team Test Strategy Profile

The main backend contract is the **Team Test Strategy Profile**. This should be
generated from repository evidence and stored as `api_repo_profile.json`.

Target shape:

```json
{
  "repo_path": "/path/to/repo",
  "primary_language": "python",
  "languages": ["python"],
  "service_frameworks": ["fastapi"],
  "build_tools": [],
  "package_managers": ["pip"],
  "api_styles": ["rest", "openapi"],
  "test_frameworks": ["pytest"],
  "mocking_frameworks": ["respx", "pytest-mock"],
  "contract_tools": ["openapi"],
  "auth_strategy": "jwt",
  "api_test_locations": ["tests/api", "tests/integration"],
  "stage_test_locations": ["tests/stage"],
  "naming_conventions": ["test_<feature>_<behavior>.py"],
  "client_patterns": ["fastapi TestClient fixture", "httpx AsyncClient"],
  "auth_helpers": ["auth_headers fixture"],
  "base_test_classes": [],
  "fixture_files": ["tests/conftest.py"],
  "test_data_builders": [],
  "api_client_helpers": [],
  "existing_ci_test_examples": [],
  "existing_stage_test_examples": [],
  "endpoint_files": [],
  "openapi_files": [],
  "graphql_schema_files": [],
  "ci_command": "pytest tests/api",
  "stage_command": "pytest tests/stage --env=stage",
  "validation_commands": [],
  "confidence": "high",
  "warnings": []
}
```

Java example:

```json
{
  "primary_language": "java",
  "service_frameworks": ["spring_boot"],
  "build_tools": ["maven"],
  "api_styles": ["rest", "openapi"],
  "test_frameworks": ["junit5", "rest_assured", "mockmvc"],
  "mocking_frameworks": ["mockito", "wiremock"],
  "auth_strategy": "jwt",
  "api_test_locations": ["src/test/java"],
  "stage_test_locations": ["src/integrationTest/java"],
  "naming_conventions": ["<Feature>ControllerTest", "<Feature>IT"],
  "client_patterns": ["MockMvc for CI", "RestAssured for stage"],
  "auth_helpers": ["JwtTestTokenFactory"],
  "fixture_files": ["src/test/java/.../fixtures"],
  "ci_command": "mvn test",
  "stage_command": "mvn verify -Pstage"
}
```

## Testing Strategy Matrix

The agent must classify scenarios into a testing strategy before code
generation:

```text
controller/api-slice
service-level
contract/schema
integration
stage smoke
stage regression
auth/security
negative/error handling
data persistence/side effect
downstream dependency behavior
```

CI tests should generally be:

```text
fast
deterministic
local
mocked or stubbed for external dependencies
safe for PR validation
```

Stage tests should generally be:

```text
environment-backed
deployed API focused
auth/config aware
allowed to verify real integrations
careful about data setup and cleanup
```

Scenarios marked `both` must generate distinct CI and stage variants when the
repo conventions require different clients, fixtures, or assertions.

## Backend Architecture

The backend implementation should follow this order:

```text
api-agent/
  app/
    schemas/
      repo_profile.py
      team_test_strategy.py
      api_scenario.py
      api_test_generation_request.py
      api_test_generation_result.py

    services/
      api_repo_context_service.py
      team_test_strategy_service.py
      api_scenario_generation_service.py
      api_test_code_generation_service.py
      api_test_file_writer.py
      generation_orchestrator.py

    strategies/
      base_strategy.py
      strategy_registry.py
      java_spring_rest_assured_strategy.py
      java_spring_mockmvc_strategy.py
      python_pytest_httpx_strategy.py
      python_fastapi_testclient_strategy.py

    tools/
      api_endpoint_scanner_tool.py
      existing_test_scanner_tool.py
      fixture_scanner_tool.py
      command_discovery_tool.py
      openapi_scanner_tool.py
      file_reader_tool.py
      file_writer_tool.py
      search_tool.py
      git_tool.py

    validation/
      validation_command_resolver.py
      repo_command_validator.py
      api_test_validator.py
```

## Strategy Registry

Generation must go through a strategy registry. The test generation agent should
not hardcode Java, Python, or any folder structure.

Each strategy must define:

```text
supports(profile) -> bool
strategy_name -> str
test_framework -> str
target_language -> str
plan_tests(request, profile) -> strategy plan
build_prompt(request, profile, examples) -> prompt
fallback_file(request, profile) -> generated file
validation_commands(profile, target) -> commands
```

Initial strategies:

```text
java_spring_rest_assured
java_spring_mockmvc
python_pytest_httpx
python_fastapi_testclient
```

The registry should return:

```text
best_strategy
confidence
reasons
warnings
```

## Backend API

Current backend scaffold:

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

Keep these endpoints for backend-first implementation. The Worktop controller
can later wrap them using the platform patterns.

## Task Lifecycle

```text
queued
running
aborting
aborted
completed
failed
```

Stage events:

```text
reading_story
scanning_repository
detecting_stack
discovering_team_strategy
finding_api_endpoints
finding_existing_tests
detecting_test_strategies
generating_scenarios
classifying_execution_targets
selecting_generation_strategy
generating_test_code
writing_files
validating
completed
failed
aborted
```

## UI Status And Frozen UI Direction

The portable Angular UI scaffold has been generated under:

```text
api-agent/frontend/test-generation/
```

The scaffold is not wired into the real Worktop Test Generation page in this
checkout because that page is not present in this repository snapshot.

The UI should stay simple and should not expose backend intelligence complexity.

Generated frontend files:

```text
api-agent/frontend/test-generation/
  test-generation.component.ts
  test-generation.component.html
  test-generation.component.scss

  functional-test-gen/
    functional-test-gen.component.ts
    functional-test-gen.component.html
    functional-test-gen.component.scss

  api-test-gen/
    api-test-gen.component.ts
    api-test-gen.component.html
    api-test-gen.component.scss

  services/
    api-test-generation.service.ts

  models/
    api-scenario.model.ts
    api-test-generation.model.ts
```

Parent Test Generation changes:

```text
test-generation.component.ts    # tab wiring only
test-generation.component.html  # Functional/API tab shell only
```

Visible API tab layout:

```text
Sprint API Stories table
Selected story context
Detected API impact panel
API scenario table
Generation target actions
  Generate CI Tests
  Generate Stage Tests
  Generate Selected Tests
Progress/status panel with Abort
Generated files summary
Validation summary
```

Scenario columns:

```text
Scenario name
API/service
Method
Endpoint
Scenario type
Testing strategy
Execution target: CI, Stage, Both
Priority
Reason
Action
```

## Implementation Phases

### Phase 1: Backend Strategy Foundation

- Expand `RepoProfile` and add `TeamTestStrategyProfile`.
- Add Java/Python stack detectors.
- Add fixture/helper/mock/auth scanner.
- Add command discovery.
- Add existing test example extraction.
- Add strategy registry.
- Replace Java-only fallback with strategy-specific Java/Python fallbacks.
- Update prompts to include strategy profile and examples.

### Phase 2: Backend Generation Quality

- Generate CI and stage variants differently.
- Use existing examples as style anchors.
- Read endpoint/controller source and nearby service/source context.
- Detect controller/route dependencies that need mocks, stubs, dependency overrides, or WireMock/respx/responses setup.
- Reuse existing fixture/auth/client helpers instead of inventing new ones.
- Generate missing mocks/stubs only when existing helpers are not available.
- Resolve output paths from team strategy profile.
- Add validation command resolver.
- Add compile/import validation for Java and Python.
- Publish strategy, confidence, warnings, reused examples, mock/stub plan, files, and validation through SSE.

### Phase 3: UI

- Generated portable API Test Generation tab scaffold.
- Generated story context, scenario table, progress panel, Abort, generated files, strategy, mocks/stubs, and validation summary.
- Remaining work: wire scaffold into the actual Worktop Test Generation page once that frontend module is available in the repo.

### Phase 4: Worktop Integration

- Wrap routes with JWT permission and API envelope.
- Reuse DB session dependency.
- Load testcase/story data through existing DAOs.
- Prepend shared story setup/API setup steps.
- Reuse existing local workspace path resolution.
- Reuse existing logging and model config conventions.

## Acceptance Criteria For Backend-First Work

Before UI work starts, the backend should be able to:

```text
1. Scan a Java repo and produce a credible team test strategy profile.
2. Scan a Python repo and produce a credible team test strategy profile.
3. Pick a generation strategy based on repo evidence.
4. Generate a CI test into the correct existing test location.
5. Generate a stage test into the correct existing test location.
6. Reuse existing fixture/auth/mock/client examples in prompts.
7. Detect controller/route dependencies and create a mock/stub plan.
8. Report confidence and warnings when conventions are unclear.
9. Publish progress and support abort.
10. Return generated files, reused examples, mock/stub plan, and validation summary.
```

## Integration With Worktop

Reuse platform mechanisms when this service is embedded in Worktop:

- JWT permission check in the parent controller layer.
- API envelope in the parent controller layer.
- DB session dependency.
- Existing model configuration DAO.
- Existing `DefaultLLMClient` and `ModelClientFactory`.
- Existing custom logger imports.
- Existing local workspace path resolution.
- Existing task manager/SSE conventions.

This folder owns API-specific intelligence and generation behavior only.
