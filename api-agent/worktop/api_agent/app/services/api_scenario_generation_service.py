from __future__ import annotations

from worktop.api_agent.app.agents.scenario_agent import ScenarioAgent
from worktop.api_agent.app.schemas.api_scenario import ApiScenario
from worktop.api_agent.app.schemas.execution_target import ExecutionTarget
from worktop.api_agent.app.schemas.api_scenario_request import GenerateApiScenariosRequest
from worktop.api_agent.app.schemas.api_scenario_result import ApiScenarioGenerationResult
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.utils.logging_utils import log_step


class ApiScenarioGenerationService:
    def __init__(self, agent: ScenarioAgent) -> None:
        self.agent = agent

    def generate(
        self,
        task_id: str,
        request: GenerateApiScenariosRequest,
        profile: RepoProfile,
        repo_understanding=None,
    ) -> ApiScenarioGenerationResult:
        output = self.agent.generate(request, profile, repo_understanding)
        scenarios, guard_warnings, review_reasons = self._guard_scenarios(
            output.scenarios, profile
        )
        if any("SCAFFOLD" in warning for warning in output.warnings):
            review_reasons.append(
                "Scenario plan is a deterministic scaffold, not story-derived "
                "coverage; it must be reviewed before use."
            )
        warnings = [*profile.warnings, *output.warnings, *guard_warnings]
        return ApiScenarioGenerationResult(
            task_id=task_id,
            user_story_hierarchy_id=request.user_story_hierarchy_id,
            user_story_id=request.user_story_id,
            scenarios=scenarios,
            repo_findings=profile.findings,
            warnings=warnings,
            needs_review=bool(review_reasons),
            review_reasons=review_reasons,
        )

    def _guard_scenarios(
        self,
        scenarios: list[ApiScenario],
        profile: RepoProfile,
    ) -> tuple[list[ApiScenario], list[str], list[str]]:
        """Deterministic scenario-plan checks.

        Drops scenarios that cannot be acted on (no steps or no assertions,
        duplicate ids) and flags scenarios whose endpoint does not match anything
        detected in the repository — those still ship, because endpoint detection
        is incomplete by nature, but a reviewer should confirm them.
        """
        kept: list[ApiScenario] = []
        warnings: list[str] = []
        review_reasons: list[str] = []
        seen_ids: set[str] = set()
        detected = {
            (endpoint.method.upper(), endpoint.path)
            for endpoint in profile.endpoints
            if endpoint.method and endpoint.path
        }
        detected_paths = {path for _, path in detected}

        for scenario in scenarios:
            if scenario.api_scenario_id in seen_ids:
                warnings.append(
                    f"Dropped scenario with duplicate id `{scenario.api_scenario_id}`."
                )
                continue
            if not scenario.scenario_steps or not scenario.assertions:
                warnings.append(
                    f"Dropped scenario `{scenario.api_scenario_id}`: it has no "
                    "actionable steps or no assertions."
                )
                continue
            seen_ids.add(scenario.api_scenario_id)

            # CI/stage classification must match reality: a stage scenario in a
            # repo with no stage command, locations, or examples cannot run, so
            # it is downgraded to CI and flagged rather than shipped broken.
            strategy = profile.team_strategy
            has_stage_infra = bool(
                strategy.stage_command
                or strategy.stage_test_locations
                or strategy.existing_stage_test_examples
            )
            if scenario.execution_target != ExecutionTarget.CI and not has_stage_infra:
                original = scenario.execution_target
                scenario.execution_target = ExecutionTarget.CI
                warnings.append(
                    f"Scenario `{scenario.api_scenario_id}` was classified as "
                    f"{original} but the repository has no stage test command, "
                    "locations, or examples; downgraded to ci."
                )
                review_reasons.append(
                    f"Scenario `{scenario.api_scenario_id}` needs stage "
                    "infrastructure that was not detected in the repository."
                )
            kept.append(scenario)

            if detected and scenario.endpoint and scenario.endpoint not in detected_paths:
                review_reasons.append(
                    f"Scenario `{scenario.api_scenario_id}` targets "
                    f"{scenario.method or '?'} {scenario.endpoint}, which does not "
                    "match any detected repository endpoint."
                )

        if not kept and scenarios:
            review_reasons.append(
                "All generated scenarios were dropped by the scenario guard; "
                "the plan needs manual review."
            )
        log_step(
            "api_scenario_guard_completed",
            {
                "input_scenarios": len(scenarios),
                "kept_scenarios": len(kept),
                "warnings": len(warnings),
                "review_reasons": len(review_reasons),
            },
        )
        return kept, warnings, review_reasons
