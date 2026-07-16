# Frontend and host wiring

Test Agent does not own a complete frontend. Worktop should provide the story selector, repository
and branch selection, progress, diff review, approval, notifications, and Apply authorization.

```ts
export interface TestAgentClient {
  generate(request: GenerationRequest): Observable<GenerationResult>;
  job(id: string): Observable<GenerationJob>;
  events(id: string): Observable<GenerationEvent>;
}
```

Register a real or mock implementation through dependency injection. Components must not contain
`if (mock)` branches. Map the platform API envelope once in the client adapter and keep feature state
based on the Test Agent DTOs.

Recommended page states are `idle`, `discovering`, `planning`, `generating`, `validating`,
`needsReview`, `completed`, `failed`, and `aborted`. A review screen should show files, diff,
commands executed, validation evidence, confidence, warnings and estimated model usage.
