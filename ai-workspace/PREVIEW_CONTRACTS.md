# Combined Browser Preview Contracts

The preview combines two independently replaceable feature contracts.

## API Test Generation

Browser mocks implement the same methods as the real API services:

```text
POST /api/api-test-generation/generate-api-scenarios
POST /api/api-test-generation/generate-api-test-code
GET  /api/api-test-generation/jobs/{taskId}
GET  /api/api-test-generation/events/{taskId}
POST /api/api-test-generation/abort/{taskId}
```

Set `DEMO.useTestGenMocks=false` to use the real API-agent through the proxy. Models and fixtures
live under `api-agent/frontend/test-generation/models` and `mocks`.

## AI Workspace

The preview backend exposes the real route/service boundary with an explicit mock LLM:

```text
GET  /api/ai-workspace/bootstrap
GET  /api/ai-workspace/repositories
POST /api/ai-workspace/sessions
GET  /api/ai-workspace/sessions/{id}/messages
POST /api/ai-workspace/ask
POST /api/ai-workspace/agent/run
GET  /api/ai-workspace/agent/executions/{id}/events
GET  /api/ai-workspace/agent/executions/{id}/plan
POST /api/ai-workspace/review/keep
POST /api/ai-workspace/review/reject
POST /api/ai-workspace/apply
```

The mock LLM returns a safe staged file so backend teams can observe plan, diff, review, and Apply.
Set `AI_WORKSPACE_ALLOW_MOCK_LLM=false` and use the host DB/tenant dependencies for production.

## Worktop replacement boundary

Keep frontend component inputs/outputs and DTOs stable. Replace only providers, API prefix,
authentication/SSE transport, tenant/DB dependencies, state backend, and host navigation entries.
