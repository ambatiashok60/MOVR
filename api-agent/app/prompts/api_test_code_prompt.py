from __future__ import annotations

from app.prompts.prompt_sections import (
    render_mock_stub_plan,
    render_repo_profile,
    render_source_context,
)
from app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from app.schemas.mock_stub_plan import MockStubPlan
from app.schemas.repo_profile import RepoProfile
from app.schemas.source_context import GenerationSourceContext


def build_api_test_code_prompt(
    request: GenerateApiTestCodeRequest,
    profile: RepoProfile,
    strategy_guidance: str | None = None,
    source_context: GenerationSourceContext | None = None,
    mock_stub_plan: MockStubPlan | None = None,
) -> str:
    steps = "\n".join(f"- {step}" for step in request.scenario_steps)
    assertions = "\n".join(f"- {assertion}" for assertion in request.assertions)
    return f"""
You are generating repository-native API tests for an active sprint ticket.

Return strict JSON with this shape:
{{
  "files": [
    {{
      "relative_path": "path/from/repo/root/TestFile.java",
      "content": "full file contents",
      "test_target": "ci|stage",
      "summary": "what this file covers"
    }}
  ],
  "summary": "short generation summary",
  "warnings": []
}}

Rules:
- Write tests into the repository's existing API test conventions when detectable.
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

Selected strategy guidance:
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
""".strip()
