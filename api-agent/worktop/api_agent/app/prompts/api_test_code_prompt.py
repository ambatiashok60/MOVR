from __future__ import annotations

from worktop.api_agent.app.prompts.prompt_sections import (
    render_mock_stub_plan,
    render_repo_profile,
    render_repo_understanding,
    render_source_context,
    response_contract,
)
from worktop.api_agent.app.schemas.llm_outputs import TestCodeOutput
from worktop.api_agent.app.schemas.repo_understanding import RepoUnderstanding
from worktop.api_agent.app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from worktop.api_agent.app.schemas.mock_stub_plan import MockStubPlan
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.source_context import GenerationSourceContext


def build_api_test_code_prompt(
    request: GenerateApiTestCodeRequest,
    profile: RepoProfile,
    strategy_guidance: str | None = None,
    source_context: GenerationSourceContext | None = None,
    mock_stub_plan: MockStubPlan | None = None,
    repo_understanding: RepoUnderstanding | None = None,
    include_contract: bool = True,
) -> str:
    steps = "\n".join(f"- {step}" for step in request.scenario_steps)
    assertions = "\n".join(f"- {assertion}" for assertion in request.assertions)
    return f"""
You are generating repository-native API tests for an active sprint ticket.

Rules:
- Write tests into the repository's existing API test conventions when detectable.
- relative_path must be a test file inside the repository's test tree; never write to application source paths.
- Never overwrite application source files; only create or update test files.
- CI tests must be fast and deterministic.
- Stage tests may target deployed endpoints and integration behavior.
- Use clear assertions for status, response body, and error handling.
- Do not invent secrets.
- Include only files that should be written.
- Use existing examples as style anchors.
- If the scenario target is both, generate distinct CI and stage variants when conventions differ.
- Reuse detected fixture/auth/client helpers where possible.
- Generate or configure mocks/stubs for controller dependencies and downstream clients when needed.
- Prefer modifying/adding the smallest number of files required for a compiling useful test.
- Every dependency the mock/stub plan marks for mocking MUST actually be mocked or stubbed in CI tests.
- Spring WebClient: never deep-stub the fluent chain with Mockito; use MockWebServer or WireMock (or the repo's existing idiom).
- RestAssured CI tests: boot the app (@SpringBootTest RANDOM_PORT) and stub downstream dependencies with WireMock or @MockBean/@MockitoBean.
- Stage tests: no mocks or stubs; use the repo's real auth/config helpers against the deployed environment.

{render_repo_understanding(repo_understanding)}

Selected strategy guidance (a hint only — the discovered understanding and the
repository's own conventions win when they disagree):
{strategy_guidance or 'Use the best repository-native strategy from the profile.'}

Scenario:
- id: {request.api_scenario_id}
- name: {request.scenario_name}
- service: {request.service_name or 'unknown'}
- method: {request.method or 'unknown'}
- endpoint: {request.endpoint or 'unknown'}
- target: {request.execution_target}

Steps:
{steps or '- none provided'}

Assertions:
{assertions or '- none provided'}

Additional context:
{request.additional_context or 'none'}

{render_repo_profile(profile)}

{render_source_context(source_context)}

{render_mock_stub_plan(mock_stub_plan)}

{response_contract(TestCodeOutput) if include_contract else ''}
""".strip()
