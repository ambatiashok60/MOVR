# API contracts, SSE and mocks

```http
POST /api/playwright/generate
GET  /api/playwright/jobs/{jobId}
GET  /api/playwright/events/{jobId}
```

Preserve the job ID, stage, terminal state, file changes, validation results and review flags even if
Worktop wraps the payload in its standard envelope. SSE terminal events must be explicit:
`completed`, `failed`, or `aborted`.

```ts
class MockTestAgentClient implements TestAgentClient {
  generate(request: GenerationRequest) {
    return of({
      jobId: 'preview-job',
      status: 'needsReview',
      filesChanged: ['e2e/example.spec.ts'],
      diffSummary: 'Added one Playwright scenario',
      validation: { syntax: 'passed', execution: 'notRun' },
      needsReview: true
    });
  }
}
```

Mocks must use the same DTOs, failure codes and terminal states as production. To replace them, change
only the DI provider and API base URL. If bearer authentication is required, use authenticated
fetch-SSE rather than native `EventSource`, which cannot use Angular interceptors.
