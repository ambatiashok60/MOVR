from __future__ import annotations

from app.agents.scenario_agent import ScenarioAgent
from app.schemas.api_scenario_request import GenerateApiScenariosRequest
from app.schemas.api_scenario_result import ApiScenarioGenerationResult
from app.schemas.repo_profile import RepoProfile


class ApiScenarioGenerationService:
    def __init__(self, agent: ScenarioAgent) -> None:
        self.agent = agent

    def generate(
        self,
        task_id: str,
        request: GenerateApiScenariosRequest,
        profile: RepoProfile,
    ) -> ApiScenarioGenerationResult:
        output = self.agent.generate(request, profile)
        return ApiScenarioGenerationResult(
            task_id=task_id,
            user_story_hierarchy_id=request.user_story_hierarchy_id,
            user_story_id=request.user_story_id,
            scenarios=output.scenarios,
            repo_findings=profile.findings,
            warnings=[*profile.warnings, *output.warnings],
        )
