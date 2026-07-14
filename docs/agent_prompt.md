Implement API test-case generation by extending the existing agentic
GENERATE_TC pipeline.

Do not create a new REST endpoint, job type, queue, or SSE event model.

The POST /generate-tc request receives a new optional Boolean field:
api_test_gen.

When api_test_gen is absent or false, preserve the existing functional
generation flow exactly.

When api_test_gen is true, route to a new API test-case generation agent.

Reuse:
- JobType.GENERATE_TC
- enqueue_task
- existing job lifecycle
- existing SSE stream
- JobEvent dataclass
- ModelClientFactory
- cancellation handling
- final result envelope

The final COMPLETED event must contain generated API test cases under:

result.results.testcases

Create new API-specific files for prompts, output models, parsing,
repository discovery and the API agent. Avoid broadly refactoring the
working tc_gen_agent.py in this milestone.

The API agent must inspect repository controllers/routes, services,
request/response models, clients, security configuration, contracts,
existing integration tests, mocks and GraphQL schemas where applicable.

It must use bounded tool-calling rounds, generate an API test plan,
generate scenarios in configurable batches, validate all output with
Pydantic and avoid inventing endpoints or schemas without repository
evidence.

Before implementing persistence, trace the existing functional
persistence and final COMPLETED result builder. Return persisted API
records in the final SSE response using the same envelope.

Keep all existing functional tests passing and add tests covering:
- absent/false/true api_test_gen routing
- API output validation
- API agent failure
- SSE completion
- cancellation
- backward compatibility

At completion, report:
- files created
- files modified
- functions changed
- contracts added
- tests added
- assumptions or unresolved persistence questions