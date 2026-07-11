from __future__ import annotations

from typing import Any, Callable

from worktop.api_agent.app.agents.repo_discovery_agent import RepoDiscoveryAgent
from worktop.api_agent.app.agents.scenario_agent import ScenarioAgent
from worktop.api_agent.app.agents.test_generation_agent import TestGenerationAgent
from worktop.api_agent.app.errors import AbortRequestedError
from worktop.api_agent.app.governance.generation_budget import (
    BudgetedLLMClient,
    BudgetExceededError,
    GenerationBudget,
)
from worktop.api_agent.app.runtime.generation_runtime import GenerationRuntime
from worktop.api_agent.app.schemas.api_scenario_request import GenerateApiScenariosRequest
from worktop.api_agent.app.schemas.api_scenario_result import ApiScenarioGenerationResult
from worktop.api_agent.app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from worktop.api_agent.app.schemas.api_test_generation_result import ApiTestGenerationResult
from worktop.api_agent.app.services.api_repo_context_service import ApiRepoContextService
from worktop.api_agent.app.services.api_scenario_generation_service import ApiScenarioGenerationService
from worktop.api_agent.app.services.api_test_code_generation_service import ApiTestCodeGenerationService
from worktop.api_agent.app.services.mock_stub_planning_service import MockStubPlanningService
from worktop.api_agent.app.services.source_context_service import SourceContextService
from worktop.api_agent.app.utils.logging_utils import log_exception, log_performance, log_step

AbortCheck = Callable[[], bool]
StagePublisher = Callable[[str, str, dict[str, Any] | None], None]


class GenerationOrchestrator:
    def __init__(self, db: Any | None = None) -> None:
        self.db = db
        self.repo_context = ApiRepoContextService()
        self.source_context = SourceContextService()
        self.mock_stub_planning = MockStubPlanningService()

    @log_performance("api_agent.generate_scenarios")
    def generate_scenarios(
        self,
        task_id: str,
        request: GenerateApiScenariosRequest,
        publish: StagePublisher,
        is_abort_requested: AbortCheck,
    ) -> ApiScenarioGenerationResult:
        context = {"task_id": task_id, "repo_path": request.repo_path, "stage": "scenario_generation"}
        log_step("api_scenario_generation_started", context)
        try:
            self._check_abort(task_id, is_abort_requested)
            publish("reading_story", "Reading story and acceptance criteria", None)

            self._check_abort(task_id, is_abort_requested)
            publish("scanning_repository", "Scanning repository for API context", None)
            profile = self.repo_context.build(request.repo_path)

            self._check_abort(task_id, is_abort_requested)
            publish(
                "finding_api_endpoints",
                "Finding API endpoints and existing test conventions",
                {"endpoint_count": len(profile.endpoints), "existing_test_count": len(profile.existing_tests)},
            )
            runtime = GenerationRuntime.create(
                task_id=task_id,
                tenant_id=request.tenant_id,
                repo_path=request.repo_path,
                branch=request.branch,
                db=self.db,
            )

            budget = GenerationBudget()
            llm_client = BudgetedLLMClient(runtime.llm_client, budget)

            self._check_abort(task_id, is_abort_requested)
            publish(
                "discovering_repository",
                "Exploring repository conventions with the discovery agent",
                None,
            )
            repo_understanding = self._discover(llm_client, request.repo_path)

            self._check_abort(task_id, is_abort_requested)
            publish("generating_scenarios", "Generating API test scenarios", None)
            service = ApiScenarioGenerationService(ScenarioAgent(llm_client))
            result = service.generate(task_id, request, profile, repo_understanding)
            result.budget = budget.report()

            publish(
                "completed",
                "API scenarios generated",
                {"scenario_count": len(result.scenarios)},
            )
            return result
        except Exception as exc:
            log_exception(exc, context=context)
            raise

    @log_performance("api_agent.generate_test_code")
    def generate_test_code(
        self,
        task_id: str,
        request: GenerateApiTestCodeRequest,
        publish: StagePublisher,
        is_abort_requested: AbortCheck,
    ) -> ApiTestGenerationResult:
        context = {"task_id": task_id, "repo_path": request.repo_path, "stage": "test_code_generation"}
        log_step("api_test_code_generation_started", context)
        try:
            self._check_abort(task_id, is_abort_requested)
            publish("scanning_repository", "Scanning repository for API test conventions", None)
            profile = self.repo_context.build(request.repo_path)

            self._check_abort(task_id, is_abort_requested)
            publish(
                "classifying_execution_targets",
                f"Preparing {request.execution_target} test generation",
                {"target": str(request.execution_target)},
            )

            self._check_abort(task_id, is_abort_requested)
            publish("extracting_existing_examples", "Finding closest existing tests and source context", None)
            source_context = self.source_context.build(request, profile)

            self._check_abort(task_id, is_abort_requested)
            publish(
                "planning_mocks_and_stubs",
                "Planning mocks, stubs, fixtures, and dependency overrides",
                {
                    "example_count": len(source_context.existing_test_examples),
                    "source_file_count": len(source_context.endpoint_sources),
                    "fixture_count": len(source_context.fixture_snippets),
                    "warnings": source_context.warnings,
                },
            )
            mock_stub_plan = self.mock_stub_planning.plan(profile, source_context)

            runtime = GenerationRuntime.create(
                task_id=task_id,
                tenant_id=request.tenant_id,
                repo_path=request.repo_path,
                branch=request.branch,
                db=self.db,
            )

            self._check_abort(task_id, is_abort_requested)
            publish(
                "discovering_repository",
                "Exploring repository conventions with the discovery agent",
                None,
            )
            budget = GenerationBudget()
            llm_client = BudgetedLLMClient(runtime.llm_client, budget)
            repo_understanding = self._discover(llm_client, request.repo_path)

            self._check_abort(task_id, is_abort_requested)
            publish("selecting_generation_strategy", "Selecting repository-native generation strategy", None)

            self._check_abort(task_id, is_abort_requested)
            publish("generating_test_code", "Generating repository-native API tests", None)
            service = ApiTestCodeGenerationService(TestGenerationAgent(llm_client))
            result = service.generate(
                task_id,
                request,
                profile,
                source_context=source_context,
                mock_stub_plan=mock_stub_plan,
                repo_understanding=repo_understanding,
            )
            result.budget = budget.report()

            self._check_abort(task_id, is_abort_requested)
            publish(
                "writing_files",
                "Generated files written to workspace",
                {
                    "files": [file.model_dump() for file in result.generated_files],
                    "strategy_name": result.strategy_name,
                    "strategy_confidence": result.strategy_confidence,
                    "strategy_reasons": result.strategy_reasons,
                    "reused_examples": [example.path for example in result.reused_examples],
                    "source_files_used": [source.path for source in result.source_files_used],
                    "mock_stub_plan": (
                        result.mock_stub_plan.model_dump()
                        if result.mock_stub_plan
                        else None
                    ),
                    "warnings": result.warnings,
                },
            )
            if result.validation:
                publish(
                    "validating",
                    result.validation.summary,
                    result.validation.model_dump(),
                )

            publish(
                "completed",
                "API test generation completed",
                {"file_count": len(result.generated_files)},
            )
            return result
        except Exception as exc:
            log_exception(exc, context=context)
            raise

    def _discover(self, llm_client, repo_path: str):
        """Best-effort model-directed discovery; failure never blocks generation.

        Budget escalations are the one exception: they must stop the run.
        """
        try:
            return RepoDiscoveryAgent(llm_client).discover(repo_path)
        except BudgetExceededError:
            raise
        except Exception as exc:
            log_exception(exc, context={"stage": "repo_discovery", "repo_path": repo_path})
            return None

    def _check_abort(self, task_id: str, is_abort_requested: AbortCheck) -> None:
        if is_abort_requested():
            raise AbortRequestedError(task_id)
