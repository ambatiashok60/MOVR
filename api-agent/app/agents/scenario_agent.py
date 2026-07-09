from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.prompts.api_scenario_prompt import build_api_scenario_prompt
from app.schemas.api_scenario import ApiScenario
from app.schemas.api_scenario_request import GenerateApiScenariosRequest
from app.schemas.execution_target import ExecutionTarget
from app.schemas.llm_outputs import ScenarioPlanOutput
from app.schemas.repo_profile import RepoProfile


class ScenarioAgent(BaseAgent):
    agent_name = "api_scenario_agent"

    def generate(
        self,
        request: GenerateApiScenariosRequest,
        profile: RepoProfile,
    ) -> ScenarioPlanOutput:
        self.log_start("generating_scenarios", story_id=request.user_story_id)
        prompt = build_api_scenario_prompt(request, profile)
        try:
            output = self.complete_structured(prompt, ScenarioPlanOutput)
        except Exception:
            output = self._fallback_plan(request, profile)
        if output.scenarios:
            return output
        return self._fallback_plan(request, profile)

    def _fallback_plan(
        self,
        request: GenerateApiScenariosRequest,
        profile: RepoProfile,
    ) -> ScenarioPlanOutput:
        endpoint = profile.endpoints[0] if profile.endpoints else None
        method = endpoint.method if endpoint else "POST"
        path = endpoint.path if endpoint else "/api/resource"
        service = endpoint.service_name if endpoint else "ApiService"
        base_name = request.story_title or request.user_story_id or "API behavior"
        scenarios = [
            ApiScenario(
                api_scenario_id="happy-path-ci",
                scenario_name=f"{base_name} happy path",
                scenario_type="positive",
                service_name=service,
                method=method,
                endpoint=path,
                priority="high",
                execution_target=ExecutionTarget.CI,
                reason="Fast deterministic validation belongs in PR CI.",
                scenario_steps=[
                    "Build a valid request from the story acceptance criteria.",
                    "Call the API entry point or controller/service layer.",
                    "Verify successful status and response contract.",
                ],
                assertions=["Response status is successful", "Required response fields are present"],
            ),
            ApiScenario(
                api_scenario_id="negative-validation-ci",
                scenario_name=f"{base_name} validation failure",
                scenario_type="negative",
                service_name=service,
                method=method,
                endpoint=path,
                priority="high",
                execution_target=ExecutionTarget.CI,
                reason="Input validation and error contracts should fail fast in CI.",
                scenario_steps=[
                    "Build an invalid request for a required field or rule.",
                    "Call the API entry point.",
                    "Verify validation error status and message.",
                ],
                assertions=["Response status is 4xx", "Error body contains a useful reason"],
            ),
            ApiScenario(
                api_scenario_id="deployed-integration-stage",
                scenario_name=f"{base_name} deployed integration",
                scenario_type="contract",
                service_name=service,
                method=method,
                endpoint=path,
                priority="medium",
                execution_target=ExecutionTarget.STAGE,
                reason="Environment-backed dependency behavior is best validated in stage.",
                scenario_steps=[
                    "Call the deployed stage API with authorized credentials.",
                    "Verify response contract and persisted/integrated behavior.",
                ],
                assertions=["Stage response matches expected contract"],
            ),
        ]
        return ScenarioPlanOutput(
            scenarios=scenarios,
            warnings=["Used deterministic fallback scenario planning because model output was unavailable."],
        )
