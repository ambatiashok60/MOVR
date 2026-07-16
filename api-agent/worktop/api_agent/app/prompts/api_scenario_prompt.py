from __future__ import annotations

from worktop.api_agent.app.prompts.prompt_sections import (
    render_repo_profile,
    render_repo_understanding,
    response_contract,
)
from worktop.api_agent.app.schemas.api_scenario_request import GenerateApiScenariosRequest
from worktop.api_agent.app.schemas.llm_outputs import ScenarioPlanOutput
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.repo_understanding import RepoUnderstanding


def build_api_scenario_prompt(
    request: GenerateApiScenariosRequest,
    profile: RepoProfile,
    repo_understanding: RepoUnderstanding | None = None,
    include_contract: bool = True,
) -> str:
    criteria = "\n".join(f"- {item}" for item in request.acceptance_criteria)
    return f"""
You are generating API test scenarios for an active sprint development ticket.

Rules:
- Ground every scenario in a detected endpoint when one matches; do not invent endpoints that contradict the detected list.
- Every scenario needs concrete scenario_steps and at least one meaningful assertion.
- Give each scenario a stable kebab-case api_scenario_id and a reason explaining its execution target.
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

{render_repo_understanding(repo_understanding)}

{render_repo_profile(profile)}

{response_contract(ScenarioPlanOutput) if include_contract else ''}
""".strip()
