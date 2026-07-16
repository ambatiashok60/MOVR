# Routes, SSE, mocks and real APIs

```http
POST /api/api-test-generation/generate-api-scenarios
POST /api/api-test-generation/generate-api-test-code
GET  /api/api-test-generation/jobs/{taskId}
POST /api/api-test-generation/abort/{taskId}
GET  /api/api-test-generation/events/{taskId}
```

Events contain `task_id`, `event_type`, `stage`, `message`, `payload`, and `created_at`; terminal event
types are `completed`, `failed`, and `aborted`. The client should reconnect with bounded retry and
then reconcile state through the job endpoint.

The preview registers providers from `provide-api-test-generation-mocks.ts`. Set
`DEMO.useTestGenMocks` to `false`, configure `API_TEST_GENERATION_PREFIX`, and replace only those
providers to use production. Mock handlers must cover success, review, validation failure, abort and
SSE terminal states. With bearer auth, use authenticated fetch-SSE or cookie auth; native
`EventSource` does not inherit Angular interceptors.
