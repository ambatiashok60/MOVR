from __future__ import annotations

from typing import Any

from worktop.core_services.app.utility.custom_logger.log_helpers import (
    log_card_simple,
    log_exception,
    log_metric,
    log_step,
)
from worktop.core_services.app.utility.custom_logger.logging import (
    log_performance,
    logger,
)

from app.agents.critic_agent import CriticAgent
from app.agents.functional_intent_agent import FunctionalIntentAgent
from app.agents.locator_reasoning_agent import LocatorReasoningAgent
from app.errors import UnsupportedRepositoryError
from app.patching.scoped_patch_writer import ScopedPatchWriter
from app.runtime.generation_runtime import GenerationRuntime
from app.schemas.decision_trace import DecisionTrace
from app.schemas.generation_request import GenerationRequest
from app.schemas.generation_result import GenerationResult
from app.services.behavioral_inventory_service import BehavioralInventoryService
from app.services.code_generation_service import CodeGenerationService
from app.services.flow_merge_service import FlowMergeService
from app.services.inventory_service import InventoryService
from app.services.ownership_resolution_service import OwnershipResolutionService
from app.services.playwright_ui_intelligence_service import PlaywrightUiIntelligenceService
from app.services.repo_strategy_service import RepoStrategyService
from app.services.result_builder_service import ResultBuilderService
from app.services.source_intelligence_service import SourceIntelligenceService
from app.services.spec_placement_service import SpecPlacementService
from app.services.technology_intelligence_service import TechnologyIntelligenceService
from app.services.test_action_service import TestActionService
from app.services.test_file_classifier_service import TestFileClassifierService
from app.validation.repo_command_validator import RepoCommandValidator


class GenerationOrchestrator:
    def __init__(self, db: Any | None = None) -> None:
        self.db = db
        self.repo_strategy = RepoStrategyService()
        self.technology = TechnologyIntelligenceService()
        self.classifier = TestFileClassifierService()
        self.inventory = InventoryService()
        self.behavioral_inventory = BehavioralInventoryService()
        self.ui_intelligence = PlaywrightUiIntelligenceService()
        self.flow_merge = FlowMergeService()
        self.patch_writer = ScopedPatchWriter()
        self.validator = RepoCommandValidator()
        self.results = ResultBuilderService()

    @log_performance("generation_orchestrator.generate")
    def generate(self, request: GenerationRequest) -> GenerationResult:
        context = {"job_id": request.job_id, "repo_path": request.repo_path, "stage": "generation"}
        log_step("generation_job_started", context)
        try:
            repo_profile = self.repo_strategy.detect(request.repo_path, request.branch)
            if repo_profile.support_status == "unsupported":
                raise UnsupportedRepositoryError(repo_profile)

            runtime = GenerationRuntime.from_request(request, db=self.db)
            functional_intent = FunctionalIntentAgent(llm_client=runtime.llm_client)
            source_intelligence = SourceIntelligenceService(llm_client=runtime.llm_client)
            spec_placement = SpecPlacementService(llm_client=runtime.llm_client)
            test_action = TestActionService(llm_client=runtime.llm_client)
            flow_merge = FlowMergeService(llm_client=runtime.llm_client)
            ownership = OwnershipResolutionService(llm_client=runtime.llm_client)
            locators = LocatorReasoningAgent(llm_client=runtime.llm_client)
            code_generation = CodeGenerationService(llm_client=runtime.llm_client)
            critic = CriticAgent(llm_client=runtime.llm_client)

            self.technology.detect(repo_profile)
            classifications = self.classifier.classify(request.repo_path)
            inventory = self.inventory.build(request.repo_path, classifications)
            ui_context = self.ui_intelligence.build(request.repo_path, inventory, repo_profile)
            intent = functional_intent.extract(request)
            source = source_intelligence.map(intent, ui_context)
            behavior = self.behavioral_inventory.extract(inventory)
            placement = spec_placement.decide(inventory, intent, ui_context)
            action = test_action.decide(placement, behavior, ui_context)
            flow_merge.plan(intent)
            ownership.resolve(inventory)
            locators.decide(source)
            patches = code_generation.generate(placement, action, ui_context)
            patches = critic.review(patches, ui_context)
            patch_result = self.patch_writer.apply(request.repo_path, patches)
            validation = (
                self.validator.validate(request.repo_path, patches, ui_context)
                if request.run_validation
                else None
            )
            decision_trace = [
                trace
                for trace in (
                    placement.decision_trace,
                    action.decision_trace,
                )
                if isinstance(trace, DecisionTrace)
            ]
            return self.results.build(
                request,
                patches,
                patch_result,
                validation,
                decision_trace,
                repo_profile,
            )
        except Exception as exc:
            log_exception(exc, context=context)
            raise
