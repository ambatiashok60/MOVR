from __future__ import annotations

from app.prompts.prompt_sections import render_repo_profile
from app.schemas.api_scenario_request import GenerateApiScenariosRequest
from app.schemas.repo_profile import RepoProfile


def build_api_scenario_prompt(
    request: GenerateApiScenariosRequest,
    profile: RepoProfile,
) -> str:
    criteria = "\n".join(f"- {item}" for item in request.acceptance_criteria)
    return f"""
You are generating API test scenarios for an active sprint development ticket.

Return strict JSON with this shape:
{{
  "scenarios": [
    {{
      "api_scenario_id": "stable-kebab-id",
      "scenario_name": "...",
      "scenario_type": "positive|negative|contract|auth|edge",
      "service_name": "...",
      "method": "GET|POST|PUT|PATCH|DELETE",
      "endpoint": "/path",
      "priority": "high|medium|low",
      "execution_target": "ci|stage|both",
      "reason": "why this belongs in CI, stage, or both",
      "scenario_steps": ["..."],
      "assertions": ["..."]
    }}
  ],
  "warnings": []
}}

Prefer CI for fast deterministic service/controller/contract tests.
Prefer stage for deployed environment tests, auth, data persistence, or downstream integration checks.
Use both when the behavior is core enough to verify in PR and deployed environments.

Story:
- hierarchy id: {request.user_story_hierarchy_id}
- story id: {request.user_story_id or 'unknown'}
- title: {request.story_title or 'unknown'}
- description: {request.story_description or 'unknown'}

Acceptance criteria:
{criteria or '- none provided'}

Additional context:
{request.additional_context or 'none'}

{render_repo_profile(profile)}
""".strip()
