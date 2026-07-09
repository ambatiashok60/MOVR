# API Test Generation Frontend Scaffold

This folder contains an integration-ready Angular scaffold for adding API Test
Generation inside an existing Test Generation page.

It is not wired into the real Worktop frontend in this repository snapshot
because the host Test Generation page is not present here.

## Files

```text
test-generation.component.*              parent tab shell
functional-test-gen/*                    placeholder for existing functional tab
api-test-gen/*                           API test generation tab
models/api-scenario.model.ts             scenario/story models
models/api-test-generation.model.ts      job/result/progress models
services/api-test-generation.service.ts  backend API + SSE client
```

## Host Integration

When the real Test Generation frontend is available:

```text
1. Keep existing functional generation component as-is.
2. Add the API Test Generation tab beside it.
3. Pass selected sprint stories into app-api-test-gen.
4. Configure API_TEST_GENERATION_PREFIX if the host API base path differs.
5. Reuse host auth/interceptor setup for HTTP and SSE requests.
```
