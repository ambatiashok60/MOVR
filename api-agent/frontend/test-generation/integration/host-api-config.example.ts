// REFERENCE ONLY.

// HOST APP app.config.ts:
// Keep the application's existing provideHttpClient(withInterceptors(...)) setup.
// Do not register a second HttpClient just for API Test Generation.

// HOST APP environment/API config:
// Replace API_TEST_GENERATION_PREFIX in api-test-generation.service.ts with the host's
// environment/API-base provider if the backend is not exposed at /api/api-test-generation.

// HOST APP authentication:
// Angular HttpClient interceptors cover REST calls. Native EventSource does not accept a
// bearer Authorization header, so use cookie authentication or replace the events service
// with the host application's authenticated fetch-based SSE implementation.
export {};
