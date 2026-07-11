# Routes, SSE, mocks and real services

```http
GET  /api/ai-workspace/bootstrap
POST /api/ai-workspace/workspace/validate
GET  /api/ai-workspace/repositories
POST /api/ai-workspace/sessions
GET  /api/ai-workspace/sessions/{id}/messages
POST /api/ai-workspace/ask
POST /api/ai-workspace/agent/run
GET  /api/ai-workspace/agent/executions/{id}
GET  /api/ai-workspace/agent/executions/{id}/events
GET  /api/ai-workspace/agent/executions/{id}/plan
POST /api/ai-workspace/review/keep
POST /api/ai-workspace/review/reject
POST /api/ai-workspace/apply
```

Frontend mocks are registered as DI replacements for workspace, agent and review services and must
return the same `ExecutionRun`, `AgentPlan`, `FileChange`, event and error DTOs as production. Disable
mock providers and configure the real API prefix to integrate. Production async execution should
return an execution ID immediately, persist buffered events, support replay/cancellation, and use
Redis/Valkey fanout. Use authenticated fetch-SSE when bearer tokens are required.
