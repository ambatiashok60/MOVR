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
uvicorn app.main:app --reload --port 8091
```
