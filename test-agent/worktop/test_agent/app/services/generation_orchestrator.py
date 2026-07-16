from __future__ import annotations

import logging
import posixpath
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Any

from worktop.test_agent.app.adapters.adapter_registry import default_adapter_registry
from worktop.test_agent.app.agents.critic_agent import CriticAgent
from worktop.test_agent.app.agents.functional_intent_agent import FunctionalIntentAgent
from worktop.test_agent.app.agents.locator_reasoning_agent import LocatorReasoningAgent
from worktop.test_agent.app.agents.repair_agent import RepairAgent
from worktop.test_agent.app.config import settings
from worktop.test_agent.app.coverage.coverage_preservation_service import CoveragePreservationService
from worktop.test_agent.app.errors import UnsupportedRepositoryError
from worktop.test_agent.app.governance.generation_budget import (
    BudgetedLLMClient,
    BudgetExceededError,
    GenerationBudget,
)
from worktop.test_agent.app.policy.repository_policy_service import RepositoryPolicyService
from worktop.test_agent.app.schemas.behavioral_test_unit import (
    AnchorFlowContext,
    BehavioralTestUnit,
    ExistingTestContext,
)
from worktop.test_agent.app.schemas.code_patch import PatchSet, PatchWriteResult
from worktop.test_agent.app.runtime.generation_runtime import GenerationRuntime
from worktop.test_agent.app.schemas.decision_trace import DecisionTrace
from worktop.test_agent.app.schemas.generation_request import GenerationRequest
from worktop.test_agent.app.schemas.generation_result import GenerationResult
from worktop.test_agent.app.schemas.playwright_ui_context import PlaywrightUiContext
from worktop.test_agent.app.schemas.repository_policy import RepositoryPolicy
from worktop.test_agent.app.schemas.test_action_decision import TestActionDecision, TestActions
from worktop.test_agent.app.services.bootstrap_scaffold_service import BootstrapScaffoldService
from worktop.test_agent.app.services.code_generation_service import CodeGenerationService
from worktop.test_agent.app.services.flow_merge_service import FlowMergeService
from worktop.test_agent.app.services.generation_manifest_service import GenerationManifestService
from worktop.test_agent.app.services.idempotency_service import IdempotencyService
from worktop.test_agent.app.services.ownership_resolution_service import OwnershipResolutionService
from worktop.test_agent.app.services.playwright_ui_intelligence_service import PlaywrightUiIntelligenceService
from worktop.test_agent.app.services.result_builder_service import ResultBuilderService
from worktop.test_agent.app.services.review_report_service import ReviewReportService
from worktop.test_agent.app.services.source_intelligence_service import SourceIntelligenceService
from worktop.test_agent.app.services.spec_placement_service import SpecPlacementService
from worktop.test_agent.app.services.technology_intelligence_service import TechnologyIntelligenceService
from worktop.test_agent.app.services.test_action_service import TestActionService
from worktop.test_agent.app.services.test_value_service import TestValueService
from worktop.test_agent.app.tools.playwright_parser_tool import PlaywrightParserTool
from worktop.test_agent.app.services.traceability_service import TraceabilityService
from worktop.test_agent.app.schemas.validation_result import ValidationCheck, ValidationResult
from worktop.test_agent.app.workspace.workspace_manager import JobWorkspace, WorkspaceManager
from worktop.core_services.app.utility.custom_logger.logging import logger

BANNER = "=" * 60



class GenerationOrchestrator:
    def __init__(self, db: Any | None = None) -> None:
        self.db = db
        self.adapters = default_adapter_registry()
        self.adapter = self.adapters.resolve(settings.default_technology)
        self.technology = TechnologyIntelligenceService()
        self.ui_intelligence = PlaywrightUiIntelligenceService()
        self.flow_merge = FlowMergeService()
        self.bootstrap = BootstrapScaffoldService()
        self.results = ResultBuilderService()
        self.coverage = CoveragePreservationService()
        self.test_value = TestValueService()
        self.traceability = TraceabilityService()
        self.review_report = ReviewReportService()
        self.policy = RepositoryPolicyService()
        self.manifest = GenerationManifestService()
        self.workspaces = WorkspaceManager()
        self.idempotency = IdempotencyService()

    @property
    def patch_writer(self) -> Any:
        return self.adapter.patch_writer

    @patch_writer.setter
    def patch_writer(self, value: Any) -> None:
        self.adapter.patch_writer = value

    @property
    def validator(self) -> Any:
        return self.adapter.validator

    @validator.setter
    def validator(self, value: Any) -> None:
        self.adapter.validator = value

    def generate(self, request: GenerationRequest) -> GenerationResult:
        context = {"job_id": request.job_id, "repo_path": request.repo_path, "stage": "generation"}
        generation_started_at = perf_counter()
        review_reasons: list[str] = []
        workspace: JobWorkspace | None = None
        logger.info(
            "\n%s\nPlaywright Test Generation\n%s\n\n"
            "Job: %s\nRepository: %s\nStory: %s",
            BANNER,
            BANNER,
            request.job_id,
            request.repo_path,
            request.test_case_name,
        )
        try:
            repo_profile = self._run_stage(
                request.job_id,
                "repo_strategy",
                lambda: self.adapter.analyze_repository(request.repo_path, request.branch),
                started={"repo": request.repo_path, "branch": request.branch or "default"},
                completed=lambda profile: {"support_status": profile.support_status},
            )
            if repo_profile.support_status == "unsupported":
                self._log_stage(request.job_id, "repo_strategy", "failed", "unsupported_repository")
                raise UnsupportedRepositoryError(repo_profile)

            workspace = self._run_stage(
                request.job_id,
                "workspace_acquire",
                lambda: self.workspaces.acquire(request.job_id, request.repo_path),
                completed=lambda acquired: {"workspace": str(acquired.root)},
            )

            repository_policy = self._run_stage(
                request.job_id,
                "repository_policy",
                lambda: self.policy.load(request.repo_path),
                completed=lambda loaded: {"source": loaded.source},
            )

            runtime = self._run_stage(
                request.job_id,
                "runtime",
                lambda: GenerationRuntime.from_request(request, db=self.db),
                started={"action": "creating_llm_client"},
            )
            budget = GenerationBudget()
            llm_client = BudgetedLLMClient(runtime.llm_client, budget)
            functional_intent = FunctionalIntentAgent(llm_client=llm_client)
            source_intelligence = SourceIntelligenceService(llm_client=llm_client)
            spec_placement = SpecPlacementService(llm_client=llm_client)
            test_action = TestActionService(llm_client=llm_client)
            flow_merge = FlowMergeService(llm_client=llm_client)
            ownership = OwnershipResolutionService(llm_client=llm_client)
            locators = LocatorReasoningAgent(llm_client=llm_client)
            code_generation = CodeGenerationService(llm_client=llm_client)
            critic = CriticAgent(llm_client=llm_client)
            repair = RepairAgent(llm_client=llm_client)

            self._run_stage(
                request.job_id,
                "technology_intelligence",
                lambda: self.technology.detect(repo_profile),
            )

            classifications = self._run_stage(
                request.job_id,
                "test_file_classification",
                lambda: self.adapter.classify_test_files(request.repo_path),
                completed=lambda files: {"classified_files": len(files)},
            )

            inventory = self._run_stage(
                request.job_id,
                "repository_inventory",
                lambda: self.adapter.build_inventory(request.repo_path, classifications),
                completed=lambda built: {
                    "test_files": len(built.test_files),
                    "page_objects": len(built.page_objects),
                },
            )

            generation_fingerprint = self.idempotency.fingerprint(request, inventory)
            existing_record = self._run_optional_stage(
                request.job_id,
                "idempotency_check",
                lambda: self.idempotency.find(generation_fingerprint),
            )
            if existing_record is not None:
                replay = self.idempotency.replay_result(request, existing_record)
                logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'generation', 'idempotent_replay', {'job_id': request.job_id, 'original_job': existing_record.job_id, 'fingerprint': generation_fingerprint})
                return replay

            ui_context = self._run_stage(
                request.job_id,
                "playwright_ui_intelligence",
                lambda: self.ui_intelligence.build(request.repo_path, inventory, repo_profile),
                completed=lambda context: {
                    "routes": len(context.routes),
                    "ui_elements": len(context.ui_elements),
                    "mocks": len(context.mock_patterns),
                    "auth": len(context.auth_session_patterns),
                },
            )

            intent = self._run_stage(
                request.job_id,
                "functional_intent",
                lambda: functional_intent.extract(request),
                completed=lambda extracted: {
                    "capability": extracted.capability or "unknown",
                    "assertions": len(extracted.assertions),
                },
            )

            source = self._run_stage(
                request.job_id,
                "source_mapping",
                lambda: source_intelligence.map(intent, ui_context),
                completed=lambda mapped: {
                    "components": len(mapped.components),
                    "locators": len(mapped.locator_evidence),
                    "routes": len(mapped.routes),
                },
            )

            behavior = self._run_stage(
                request.job_id,
                "behavioral_inventory",
                lambda: self.adapter.build_flow_inventory(inventory),
                completed=lambda candidates: {"candidate_tests": len(candidates)},
            )

            placement = self._run_stage(
                request.job_id,
                "spec_placement",
                lambda: spec_placement.decide(inventory, intent, ui_context),
                completed=lambda decision: {
                    "target": decision.target_spec_file,
                    "create_new": decision.create_new,
                    "confidence": decision.confidence,
                    "evidence": len(decision.decision_trace.evidence),
                },
            )

            placement = self._normalize_bootstrap_placement(repo_profile, placement)
            target_behavior = self._behavior_for_placement(placement, behavior)
            logger.info(
                "[playwright-generation] stage=context_scope status=selected "
                "target_spec=%s create_new=%s target_tests=%s repository_tests=%s",
                placement.target_spec_file,
                placement.create_new,
                [unit.test_title for unit in target_behavior],
                len(behavior),
            )

            action = self._run_stage(
                request.job_id,
                "test_action_decision",
                lambda: test_action.decide(
                    placement, target_behavior, intent, ui_context, request.repo_path
                ),
                completed=lambda decision: {
                    "action": decision.action,
                    "target_test": decision.target_test_title or "none",
                    "confidence": decision.confidence,
                },
            )

            self._flag_low_placement_confidence(placement, review_reasons)
            action = self._reconcile_action_with_placement(placement, action)
            action = self._gate_action_confidence(action, review_reasons)
            self._flag_shallow_decision_trace(
                "spec_placement", placement.decision_trace, review_reasons
            )
            self._flag_shallow_decision_trace(
                "test_action", action.decision_trace, review_reasons
            )

            existing_test_context = self._run_stage(
                request.job_id,
                "existing_test_context",
                lambda: self._resolve_existing_test_context(
                    placement, action, target_behavior
                ),
                completed=lambda target: {
                    "selected": target is not None,
                    "file": target.file_path if target else "none",
                    "test_title": target.test_title if target else "none",
                    "lines": f"{target.start_line}-{target.end_line}" if target else "none",
                },
            )
            action = self._ensure_safe_extension_action(action, existing_test_context)

            anchor_flow_context = self._run_stage(
                request.job_id,
                "anchor_flow_context",
                lambda: self._resolve_anchor_flow_context(
                    placement,
                    action,
                    behavior,
                    request.repo_path,
                    intent,
                    test_action.ranking_agent,
                ),
                completed=lambda anchor: {
                    "selected": anchor is not None,
                    "file": anchor.file_path if anchor else "none",
                    "anchor_test": anchor.anchor_test_title if anchor else "none",
                    "describe": anchor.describe_title if anchor else "none",
                },
            )

            flow_plan = None
            if action.action == TestActions.EXTEND_EXISTING_TEST:
                flow_plan = self._run_optional_stage(
                    request.job_id,
                    "flow_merge",
                    lambda: flow_merge.plan(intent, existing_test_context),
                )
            else:
                logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'flow_merge', 'skipped', {'action': action.action, 'reason': 'flow_merge_only_applies_to_extension'})
            self._flag_low_flow_merge_confidence(flow_plan, review_reasons)
            ownership_resolution = self._run_optional_stage(
                request.job_id,
                "ownership_resolution",
                lambda: ownership.resolve(inventory, source, intent),
            )
            self._flag_low_ownership_confidence(ownership_resolution, review_reasons)
            locator_decisions = self._run_optional_stage(
                request.job_id,
                "locator_reasoning",
                lambda: self._decide_locators_with_context(
                    locators,
                    source,
                    action,
                    anchor_flow_context,
                    intent,
                    ui_context,
                    placement.target_spec_file,
                ),
            )

            logger.info(
                "[playwright-generation] stage=code_generation context "
                "target_spec=%s action=%s extension_target=%s anchor=%s describe=%s "
                "locator_decisions=%s",
                placement.target_spec_file,
                action.action,
                existing_test_context.test_title if existing_test_context else "none",
                anchor_flow_context.anchor_test_title if anchor_flow_context else "none",
                anchor_flow_context.describe_title if anchor_flow_context else "none",
                len(locator_decisions or []),
            )
            patches = self._run_stage(
                request.job_id,
                "code_generation",
                lambda: code_generation.generate(
                    placement,
                    action,
                    ui_context,
                    existing_test_context,
                    flow_plan,
                    ownership_resolution,
                    anchor_flow_context,
                    locator_decisions,
                    request.repo_path,
                ),
                completed=lambda patch_set: {
                    "patches": len(patch_set.patches),
                    "paths": [patch.path for patch in patch_set.patches],
                },
            )

            patches = self._run_stage(
                request.job_id,
                "critic_review",
                lambda: critic.review(
                    patches, ui_context, anchor_flow_context, locator_decisions
                ),
                completed=lambda reviewed: {"patches": len(reviewed.patches)},
            )
            self._bind_append_to_anchor_describe(
                patches, anchor_flow_context, request.repo_path
            )
            self._bind_extension_target(
                patches, existing_test_context, request.repo_path
            )

            if repo_profile.requires_bootstrap:
                patches = self._run_stage(
                    request.job_id,
                    "bootstrap_scaffold",
                    lambda current=patches: self.bootstrap.merge(
                        request.repo_path,
                        repo_profile,
                        current,
                    ),
                    completed=lambda merged: {
                        "patches": len(merged.patches),
                        "paths": [patch.path for patch in merged.patches],
                    },
                )

            test_value_report = (
                self._run_optional_stage(
                    request.job_id,
                    "test_value_analysis",
                    lambda: self.test_value.evaluate(patches, target_behavior),
                )
                if settings.enable_extended_reporting
                else None
            )
            if test_value_report is not None:
                review_reasons.extend(
                    self.test_value.review_reasons(
                        test_value_report,
                        allow_full_duplicates=(
                            repository_policy.generation.allow_full_duplicates
                        ),
                    )
                )

            patch_result, validation, patches = self._write_validate_and_repair(
                request=request,
                patches=patches,
                ui_context=ui_context,
                existing_test_context=existing_test_context,
                anchor_flow_context=anchor_flow_context,
                flow_plan=flow_plan,
                ownership_resolution=ownership_resolution,
                locator_decisions=locator_decisions,
                requires_bootstrap=repo_profile.requires_bootstrap,
                critic=critic,
                repair=repair,
                policy=repository_policy,
                budget=budget,
                workspace=workspace,
            )

            coverage_report = self._assess_coverage_preservation(
                request, patches, patch_result, target_behavior, review_reasons
            )

            traceability_matrix = (
                self._run_optional_stage(
                    request.job_id,
                    "requirement_traceability",
                    lambda: self.traceability.build(
                        request, intent, patches, target_behavior
                    ),
                )
                if settings.enable_extended_reporting
                else None
            )
            if traceability_matrix is not None:
                review_reasons.extend(
                    self.traceability.review_reasons(traceability_matrix)
                )

            generation_manifest = self._run_optional_stage(
                request.job_id,
                "generation_manifest",
                lambda: self.manifest.build(
                    request,
                    inventory=inventory,
                    policy=repository_policy,
                    model_provider=(
                        settings.default_model_provider
                        or type(runtime.llm_client).__name__
                    ),
                    decisions=[
                        ("spec_placement", placement),
                        ("test_action", action),
                        ("flow_merge", flow_plan),
                        ("ownership_resolution", ownership_resolution),
                    ],
                    patches=patches,
                ),
            ) if settings.enable_extended_reporting else None

            budget_report = budget.report()
            if budget_report.review_required:
                for reason in budget_report.exceeded_thresholds:
                    message = f"Budget estimate review: {reason}"
                    if message not in review_reasons:
                        review_reasons.append(message)

            review_report = self._run_optional_stage(
                request.job_id,
                "review_report",
                lambda: self.review_report.build(
                    request,
                    placement=placement,
                    action=action,
                    flow_plan=flow_plan,
                    anchor_flow_context=anchor_flow_context,
                    existing_test_context=existing_test_context,
                    locator_decisions=locator_decisions,
                    patches=patches,
                    patch_result=patch_result,
                    validation=validation,
                    coverage=coverage_report,
                    test_value=test_value_report,
                    traceability=traceability_matrix,
                    review_reasons=review_reasons,
                ),
            ) if settings.enable_extended_reporting else None

            decision_trace = [
                trace
                for trace in (
                    placement.decision_trace,
                    action.decision_trace,
                )
                if isinstance(trace, DecisionTrace)
            ]
            result = self._run_stage(
                request.job_id,
                "result_build",
                lambda: self.results.build(
                    request,
                    patches,
                    patch_result,
                    validation,
                    decision_trace,
                    repo_profile,
                    review_reasons,
                    coverage=coverage_report,
                    test_value=test_value_report,
                    traceability=traceability_matrix,
                    review_report=review_report,
                    manifest=generation_manifest,
                    budget=budget_report,
                ),
                completed=lambda built: {
                    "files_changed": len(built.files_changed),
                    "confidence": built.confidence,
                    "needs_review": built.needs_review,
                },
            )
            result.generation_fingerprint = generation_fingerprint
            self._run_optional_stage(
                request.job_id,
                "idempotency_record",
                lambda: self.idempotency.record(generation_fingerprint, result),
            )
            logger.info(
                "\nGeneration Summary\n------------------\n"
                "Files changed: %s\nNeeds review: %s\nReview reasons: %s\n"
                "Validation: %s\n\nCompleted in %.2f seconds.",
                ", ".join(result.files_changed) or "none",
                result.needs_review,
                len(result.review_reasons),
                "passed"
                if result.validation and result.validation.passed
                else "failed"
                if result.validation
                else "not run",
                perf_counter() - generation_started_at,
            )
            return result
        except BudgetExceededError as exc:
            logger.log(logging.ERROR, "[playwright-generation] stage=%s | status=%s | details=%s", 'generation', 'escalated', {'job_id': request.job_id, 'duration_ms': round((perf_counter() - generation_started_at) * 1000, 2), 'reason': str(exc), 'usage': exc.report.usage.model_dump()})
            raise
        except Exception as exc:
            logger.log(logging.ERROR, "[playwright-generation] stage=%s | status=%s | details=%s", 'generation', 'failed', {'job_id': request.job_id, 'duration_ms': round((perf_counter() - generation_started_at) * 1000, 2), 'error': exc})
            logger.exception(
                "[playwright-generation] job_id=%s stage=generation status=failed context=%s error=%s",
                request.job_id,
                context,
                exc,
            )
            raise
        finally:
            if workspace is not None:
                self.workspaces.release(workspace)

    def _assess_coverage_preservation(
        self,
        request: GenerationRequest,
        patches: PatchSet,
        patch_result: PatchWriteResult,
        behavior: list[BehavioralTestUnit],
        review_reasons: list[str],
    ) -> Any | None:
        """Compare behavioral coverage graphs before and after the applied patches.

        Only meaningful when patches actually landed on disk; a run that failed
        plan validation before writing has nothing to compare. Removed or
        weakened coverage is flagged for review, never silently accepted.
        """
        if not patch_result.applied:
            logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'coverage_preservation', 'skipped', {'job_id': request.job_id, 'reason': 'no_patches_applied'})
            return None

        def build_report() -> Any:
            before = self.coverage.snapshot(behavior)
            after = self.coverage.snapshot_after_patches(
                request.repo_path, patches, before
            )
            return self.coverage.compare(before, after)

        report = self._run_optional_stage(
            request.job_id, "coverage_preservation", build_report
        )
        if report is not None:
            review_reasons.extend(self.coverage.review_reasons(report))
        return report

    def _run_advisory_stage(self, job_id: str, stage: str, action: Any) -> None:
        try:
            logger.info("job_id=%s stage=%s status=started", job_id, stage)
            action()
            logger.info("job_id=%s stage=%s status=completed", job_id, stage)
        except Exception:
            logger.exception(
                "Advisory stage %s failed; generation continues unaffected.", stage
            )

    def _run_optional_stage(self, job_id: str, stage: str, action: Callable[[], Any]) -> Any | None:
        """Run a best-effort stage whose result improves generation but is not required.

        Returns the stage result on success, or ``None`` if it fails, so a failure in
        an advisory-quality signal never aborts the overall generation.
        """
        try:
            logger.info("job_id=%s stage=%s status=started", job_id, stage)
            result = action()
            logger.info("job_id=%s stage=%s status=completed", job_id, stage)
            return result
        except Exception:
            logger.exception(
                "Optional stage %s failed; continuing without its result.", stage
            )
            return None

    def _log_stage(
        self,
        job_id: str,
        stage: str,
        status: str,
        detail: str | None = None,
    ) -> None:
        message = f"job_id={job_id} stage={stage} status={status}"
        if detail:
            message = f"{message} {detail}"
        logger.info(message)

    def _run_stage(
        self,
        job_id: str,
        stage: str,
        action: Callable[[], Any],
        *,
        started: dict[str, Any] | None = None,
        completed: Callable[[Any], dict[str, Any]] | None = None,
    ) -> Any:
        logger.info(
            "job_id=%s stage=%s status=started details=%s",
            job_id,
            stage,
            started or {},
        )
        result = action()
        completed_details = completed(result) if completed else {}
        logger.info(
            "job_id=%s stage=%s status=completed details=%s",
            job_id,
            stage,
            completed_details,
        )
        return result

    def _write_validate_and_repair(
        self,
        request: GenerationRequest,
        patches: PatchSet,
        ui_context: PlaywrightUiContext,
        existing_test_context: ExistingTestContext | None,
        critic: CriticAgent,
        repair: RepairAgent,
        anchor_flow_context: AnchorFlowContext | None = None,
        flow_plan: Any | None = None,
        ownership_resolution: Any | None = None,
        locator_decisions: Any | None = None,
        requires_bootstrap: bool = False,
        policy: RepositoryPolicy | None = None,
        budget: GenerationBudget | None = None,
        workspace: JobWorkspace | None = None,
    ) -> tuple[PatchWriteResult, ValidationResult | None, PatchSet]:
        patch_result = PatchWriteResult()
        max_attempts = max(settings.max_repair_attempts, 0)
        logger.info(
            "[playwright-generation] stage=patch_integration context "
            "target_paths=%s operations=%s extension_target=%s anchor=%s describe=%s",
            [patch.path for patch in patches.patches],
            [patch.operation for patch in patches.patches],
            existing_test_context.test_title if existing_test_context else "none",
            anchor_flow_context.anchor_test_title if anchor_flow_context else "none",
            anchor_flow_context.describe_title if anchor_flow_context else "none",
        )
        plan_validation = self._validate_patch_plan(
            request,
            patches,
            existing_test_context,
            anchor_flow_context,
            flow_plan,
            ownership_resolution,
            requires_bootstrap,
            attempt=0,
            policy=policy,
        )
        if not plan_validation.passed:
            patches, validation = self._repair_patch_plan(
                request=request,
                patches=patches,
                validation=plan_validation,
                ui_context=ui_context,
                existing_test_context=existing_test_context,
                anchor_flow_context=anchor_flow_context,
                flow_plan=flow_plan,
                ownership_resolution=ownership_resolution,
                locator_decisions=locator_decisions,
                requires_bootstrap=requires_bootstrap,
                critic=critic,
                repair=repair,
                max_attempts=max_attempts,
                policy=policy,
                budget=budget,
            )
            if validation is not None and not validation.passed:
                return patch_result, validation, patches

        patch_result = self._write_patches(request, patches, attempt=0, workspace=workspace)

        if not request.run_validation:
            self._log_stage(request.job_id, "validation", "skipped")
            return patch_result, None, patches

        validation = self._validate_patches(request, patches, ui_context, attempt=0)
        if validation.passed:
            return patch_result, validation, patches

        for attempt in range(1, max_attempts + 1):
            if budget is not None:
                budget.charge_repair_attempt()
            logger.log(logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", 'repair_loop', 'validation_failed', {'job_id': request.job_id, 'attempt': attempt, 'max_attempts': max_attempts, 'failed_checks': [check.name for check in validation.checks if not check.passed]})
            self._run_stage(
                request.job_id,
                "patch_rollback",
                lambda result=patch_result: self._rollback_patches(
                    request, result, workspace
                ),
                started={"attempt": attempt},
            )
            repaired_patches = self._run_stage(
                request.job_id,
                "repair_generation",
                lambda current=patches, failed=validation: repair.repair(
                    current, failed, anchor_flow_context, locator_decisions
                ),
                started={"attempt": attempt},
                completed=lambda patch_set: {
                    "attempt": attempt,
                    "patches": len(patch_set.patches),
                    "paths": [patch.path for patch in patch_set.patches],
                },
            )
            patches = self._run_stage(
                request.job_id,
                "repair_critic_review",
                lambda current=repaired_patches: critic.review(
                    current, ui_context, anchor_flow_context, locator_decisions
                ),
                started={"attempt": attempt},
                completed=lambda reviewed: {
                    "attempt": attempt,
                    "patches": len(reviewed.patches),
                },
            )
            plan_validation = self._validate_patch_plan(
                request,
                patches,
                existing_test_context,
                anchor_flow_context,
                flow_plan,
                ownership_resolution,
                requires_bootstrap,
                attempt=attempt,
                policy=policy,
            )
            if not plan_validation.passed:
                validation = plan_validation
                continue
            patch_result = self._write_patches(
                request, patches, attempt=attempt, workspace=workspace
            )
            validation = self._validate_patches(request, patches, ui_context, attempt=attempt)
            validation.repair_attempted = True
            if validation.passed:
                logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'repair_loop', 'completed', {'job_id': request.job_id, 'attempts': attempt, 'passed': True})
                return patch_result, validation, patches

        logger.log(logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", 'repair_loop', 'exhausted', {'job_id': request.job_id, 'attempts': max_attempts, 'passed': False})
        validation.repair_attempted = max_attempts > 0
        if policy is not None and policy.generation.rollback_failed_patch:
            self._run_stage(
                request.job_id,
                "patch_rollback",
                lambda result=patch_result: self._rollback_patches(
                    request, result, workspace
                ),
                started={"reason": "policy_rollback_failed_patch"},
            )
            patch_result = PatchWriteResult()
        else:
            logger.warning(
                "[playwright-generation] stage=failed_patch_retention status=retained "
                "job_id=%s paths=%s failed_checks=%s reason=debug_inspection "
                "rollback=false",
                request.job_id,
                [patch.path for patch in patch_result.applied],
                [check.name for check in validation.checks if not check.passed],
            )
        return patch_result, validation, patches

    def _behavior_for_placement(
        self,
        placement: Any,
        candidates: list[BehavioralTestUnit],
    ) -> list[BehavioralTestUnit]:
        """After placement, keep existing-file reasoning inside that spec."""
        if placement.create_new:
            return candidates
        target = str(PurePosixPath(placement.target_spec_file or "")).removeprefix("./")
        return [
            candidate
            for candidate in candidates
            if str(PurePosixPath(candidate.file_path)).removeprefix("./") == target
        ]

    def _decide_locators_with_context(
        self,
        locator_agent: Any,
        source: Any,
        action: TestActionDecision,
        anchor: AnchorFlowContext | None,
        intent: Any,
        ui_context: PlaywrightUiContext,
        target_spec: str,
    ) -> Any:
        logger.info(
            "[playwright-generation] stage=locator_reasoning context "
            "target_spec=%s action=%s anchor=%s anchor_describe=%s",
            target_spec,
            action.action,
            anchor.anchor_test_title if anchor else "none",
            anchor.describe_title if anchor else "none",
        )
        return locator_agent.decide(
            source,
            action=action,
            anchor=anchor,
            intent=intent,
            ui_context=ui_context,
        )

    def _resolve_existing_test_context(
        self,
        placement: Any,
        action: Any,
        candidates: list[BehavioralTestUnit],
    ) -> ExistingTestContext | None:
        if action.action != TestActions.EXTEND_EXISTING_TEST:
            logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'existing_test_context', 'skipped', {'action': action.action})
            return None

        target_spec = placement.target_spec_file
        target_title = action.target_test_title
        target_file = action.target_file_path or target_spec
        target_start = action.target_start_line
        normalized_target = str(PurePosixPath(target_spec or "")).removeprefix("./")
        normalized_action_file = str(PurePosixPath(target_file or "")).removeprefix("./")
        normalized_title = self._normalize_test_title(target_title)
        matches = [
            candidate
            for candidate in candidates
            if self._normalize_test_title(candidate.test_title) == normalized_title
            and (
                not target_file
                or str(PurePosixPath(candidate.file_path)).removeprefix("./")
                == normalized_action_file
            )
            and (target_start is None or candidate.start_line == target_start)
        ]
        if not matches:
            logger.log(logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", 'existing_test_context', 'missing', {'target_spec': normalized_target or 'none', 'target_test': target_title or 'none', 'target_file': normalized_action_file or 'none', 'target_start_line': target_start, 'available_tests': [(candidate.file_path, candidate.test_title, candidate.start_line) for candidate in candidates]})
            return None

        selected = matches[0]
        logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'existing_test_context', 'selected', {'file': selected.file_path, 'test_title': selected.test_title, 'lines': f'{selected.start_line}-{selected.end_line}'})

        return ExistingTestContext(
            file_path=selected.file_path,
            describe_title=selected.describe_title,
            test_title=selected.test_title,
            start_line=selected.start_line,
            end_line=selected.end_line,
            fixtures=selected.fixtures,
            page_objects=selected.page_objects,
            behavior_summary=selected.behavior_summary,
            source_excerpt=selected.source_excerpt,
        )

    def _normalize_test_title(self, title: str | None) -> str:
        return " ".join((title or "").strip().lower().split())

    def _normalize_bootstrap_placement(
        self,
        repo_profile: Any,
        placement: Any,
    ) -> Any:
        """Steer placement onto the scaffolded convention for bootstrap repos.

        A bootstrap repo has no existing specs, so the only valid placement is a
        new spec under the scaffolded ``e2e/`` testDir. The LLM decision is kept
        for the file name; the location and create_new are normalized.
        """
        if not getattr(repo_profile, "requires_bootstrap", False):
            return placement

        target = placement.target_spec_file or "generated.spec.ts"
        name = PurePosixPath(target).name
        if not name.endswith((".spec.ts", ".e2e.ts", ".pw.ts", ".playwright.ts")):
            name = f"{PurePosixPath(name).stem or 'generated'}.spec.ts"
        normalized_target = f"e2e/{name}"
        if placement.create_new and placement.target_spec_file == normalized_target:
            return placement

        logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'spec_placement', 'bootstrap_normalized', {'from_target': placement.target_spec_file, 'to_target': normalized_target, 'from_create_new': placement.create_new})
        placement.target_spec_file = normalized_target
        placement.create_new = True
        return placement

    def _flag_low_placement_confidence(
        self,
        placement: Any,
        review_reasons: list[str],
    ) -> None:
        threshold = settings.min_placement_confidence
        if placement.confidence >= threshold:
            return
        reason = (
            f"Spec placement confidence {placement.confidence:.2f} is below the "
            f"review threshold {threshold:.2f} for {placement.target_spec_file}."
        )
        review_reasons.append(reason)
        logger.log(logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", 'spec_placement', 'low_confidence_flagged', {'confidence': placement.confidence, 'threshold': threshold, 'target_spec': placement.target_spec_file})

    def _flag_shallow_decision_trace(
        self,
        stage: str,
        trace: Any | None,
        review_reasons: list[str],
    ) -> None:
        """Quality floor for LLM reasoning: a decision without a stated decision,
        justification, or evidence validates structurally but is unreviewable, so
        it is flagged (non-blocking) rather than trusted silently."""
        if trace is None:
            return
        decision = (getattr(trace, "decision", "") or "").strip()
        justification = (getattr(trace, "justification", "") or "").strip()
        evidence = getattr(trace, "evidence", None) or []
        if decision not in ("", "undecided") and justification and evidence:
            return
        review_reasons.append(
            f"{stage} decision trace lacks a decision, justification, or evidence; "
            "manual review recommended."
        )
        logger.log(logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", stage, 'shallow_decision_trace', {'decision': decision or 'empty', 'has_justification': bool(justification), 'evidence_count': len(evidence)})

    def _flag_low_flow_merge_confidence(
        self,
        flow_plan: Any | None,
        review_reasons: list[str],
    ) -> None:
        if flow_plan is None:
            return
        threshold = settings.min_flow_merge_confidence
        if flow_plan.confidence >= threshold:
            return
        reason = (
            f"Flow merge confidence {flow_plan.confidence:.2f} is below the review "
            f"threshold {threshold:.2f}; preserved flow may be incomplete."
        )
        review_reasons.append(reason)
        logger.log(logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", 'flow_merge', 'low_confidence_flagged', {'confidence': flow_plan.confidence, 'threshold': threshold})

    def _flag_low_ownership_confidence(
        self,
        ownership: Any | None,
        review_reasons: list[str],
    ) -> None:
        if ownership is None:
            return
        threshold = settings.min_ownership_confidence
        if ownership.confidence >= threshold:
            return
        reason = (
            f"Ownership resolution confidence {ownership.confidence:.2f} is below the "
            f"review threshold {threshold:.2f} for {ownership.owner_path} "
            f"(create_new={ownership.create_new})."
        )
        review_reasons.append(reason)
        logger.log(logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", 'ownership_resolution', 'low_confidence_flagged', {'confidence': ownership.confidence, 'threshold': threshold, 'owner_path': ownership.owner_path, 'create_new': ownership.create_new})

    def _gate_action_confidence(
        self,
        action: TestActionDecision,
        review_reasons: list[str],
    ) -> TestActionDecision:
        """Flag low-confidence actions and downgrade the only destructive one.

        ``extend_existing_test`` rewrites a proven test block, so a low-confidence
        extension is coerced into a non-destructive append. ``append_new_test`` and
        ``create_new_spec`` are additive, so they are flagged for review but kept.
        """
        threshold = settings.min_action_confidence
        if action.confidence >= threshold:
            return action

        review_reasons.append(
            f"Test action '{action.action}' confidence {action.confidence:.2f} is "
            f"below the review threshold {threshold:.2f}."
        )

        if action.action != TestActions.EXTEND_EXISTING_TEST:
            logger.log(logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", 'test_action_decision', 'low_confidence_flagged', {'action': action.action, 'confidence': action.confidence, 'threshold': threshold})
            return action

        capped_confidence = min(action.confidence, 0.35)
        logger.log(logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", 'test_action_decision', 'low_confidence_downgraded', {'from_action': action.action, 'to_action': TestActions.APPEND_NEW_TEST, 'confidence': action.confidence, 'threshold': threshold})
        return TestActionDecision(
            action=TestActions.APPEND_NEW_TEST,
            target_test_title=None,
            confidence=capped_confidence,
            decision_trace=DecisionTrace(
                decision=TestActions.APPEND_NEW_TEST,
                confidence=capped_confidence,
                justification=(
                    "Extension confidence was below threshold; appending a new test "
                    "avoids rewriting a proven test block on a low-confidence decision."
                ),
                evidence=[
                    f"Original action extend_existing_test confidence {action.confidence:.2f}",
                    f"min_action_confidence threshold {threshold:.2f}",
                ],
                risk="medium",
                fallback="Append a new test instead of extending under low confidence.",
            ),
        )

    def _reconcile_action_with_placement(
        self,
        placement: Any,
        action: TestActionDecision,
    ) -> TestActionDecision:
        """Coerce the test action so it is consistent with the spec-placement decision.

        Placement is the authority on the target file: if a brand-new spec is being
        created the only consistent action is ``create_new_spec``; if an existing spec
        owns the flow, ``create_new_spec`` is contradictory and is downgraded to a safe
        append into that spec.
        """
        is_create_new_spec = action.action == TestActions.CREATE_NEW_SPEC
        if placement.create_new == is_create_new_spec:
            return action

        if placement.create_new:
            coerced_action = TestActions.CREATE_NEW_SPEC
            justification = (
                "Spec placement decided to create a new spec, so the action must "
                "create it rather than extend or append an existing test."
            )
        else:
            coerced_action = TestActions.APPEND_NEW_TEST
            justification = (
                "Spec placement selected an existing owning spec, so a new-spec action "
                "is contradictory; appending a new test into that spec is the safe path."
            )

        capped_confidence = min(action.confidence, 0.4)
        logger.log(logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", 'test_action_decision', 'reconciled_with_placement', {'from_action': action.action, 'to_action': coerced_action, 'placement_create_new': placement.create_new, 'target_spec': placement.target_spec_file})
        return TestActionDecision(
            action=coerced_action,
            target_test_title=None,
            confidence=capped_confidence,
            decision_trace=DecisionTrace(
                decision=coerced_action,
                confidence=capped_confidence,
                justification=justification,
                evidence=[
                    f"Spec placement create_new={placement.create_new} "
                    f"target={placement.target_spec_file}",
                    f"Original action was {action.action}",
                ],
                risk="medium",
                fallback="Reconcile the test action to match the placement decision.",
            ),
        )

    def _resolve_anchor_flow_context(
        self,
        placement: Any,
        action: TestActionDecision,
        candidates: list[BehavioralTestUnit],
        repo_path: str = "",
        intent: Any | None = None,
        ranking_agent: Any | None = None,
    ) -> AnchorFlowContext | None:
        """Pick a sibling test in the target spec to seed an appended test's flow.

        For ``append_new_test``, parse only the placement-selected suite and rank its
        tests against the requested intent to select the best setup/style reference. For
        ``create_new_spec``, the repository behavior inventory remains useful for
        selecting a style template. The anchor is reference-only and is never patched.
        """
        if action.action == TestActions.APPEND_NEW_TEST:
            target = Path(repo_path) / placement.target_spec_file
            if not target.is_file():
                logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'anchor_flow_context', 'target_missing', {'target_spec': placement.target_spec_file})
                return None
            pool = PlaywrightParserTool().extract_tests(
                placement.target_spec_file,
                target.read_text(encoding="utf-8", errors="ignore"),
            )
            if not pool:
                logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'anchor_flow_context', 'no_tests_in_target_spec', {'target_spec': placement.target_spec_file})
                return None
            ranked = ranking_agent.rank(pool, intent) if ranking_agent is not None else []
            if ranked:
                anchor = ranked[0]
                rationale = (
                    f"Selected agent-ranked test '{anchor.test_title}' from the "
                    f"placement-selected suite {placement.target_spec_file} as the best "
                    "anchor for the requested behavior."
                )
            else:
                anchor = min(pool, key=lambda unit: unit.start_line)
                rationale = (
                    f"Selected deterministic fallback test '{anchor.test_title}' from "
                    f"the placement-selected suite {placement.target_spec_file}."
                )
        elif action.action == TestActions.CREATE_NEW_SPEC:
            pool = list(candidates)
            pool_description = "existing test(s) across the repository"
            empty_reason = "no_template_candidates_in_repository"
        else:
            logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'anchor_flow_context', 'skipped', {'action': action.action})
            return None

        if action.action == TestActions.CREATE_NEW_SPEC and not pool:
            logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'anchor_flow_context', empty_reason, {'target_spec': placement.target_spec_file})
            return None
        if action.action == TestActions.CREATE_NEW_SPEC:
            anchor = max(
                pool,
                key=lambda unit: (
                    len(unit.page_objects) + len(unit.fixtures),
                    len(unit.source_excerpt),
                    -unit.start_line,
                ),
            )
            rationale = (
                f"Selected '{anchor.test_title}' from {anchor.file_path} as the richest "
                f"reusable setup ({len(anchor.page_objects)} page object(s), "
                f"{len(anchor.fixtures)} fixture(s)) among {len(pool)} {pool_description}."
            )
        logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'anchor_flow_context', 'selected', {'file': anchor.file_path, 'anchor_test': anchor.test_title, 'page_objects': len(anchor.page_objects), 'fixtures': len(anchor.fixtures), 'pool': len(pool)})
        return AnchorFlowContext(
            file_path=anchor.file_path,
            describe_title=anchor.describe_title,
            anchor_test_title=anchor.test_title,
            fixtures=anchor.fixtures,
            page_objects=anchor.page_objects,
            behavior_summary=anchor.behavior_summary,
            source_excerpt=anchor.source_excerpt,
            rationale=rationale,
        )

    def _ensure_safe_extension_action(
        self,
        action: TestActionDecision,
        existing_test_context: ExistingTestContext | None,
    ) -> TestActionDecision:
        if (
            action.action != TestActions.EXTEND_EXISTING_TEST
            or existing_test_context is not None
        ):
            return action

        logger.log(logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", 'existing_test_context', 'downgraded_action', {'from_action': action.action, 'to_action': 'append_new_test', 'reason': 'no_valid_existing_test_context'})
        return TestActionDecision(
            action=TestActions.APPEND_NEW_TEST,
            target_test_title=None,
            confidence=min(action.confidence, 0.35),
            decision_trace=DecisionTrace(
                decision=TestActions.APPEND_NEW_TEST,
                confidence=min(action.confidence, 0.35),
                justification=(
                    "Existing-test extension was unsafe because no parser-validated "
                    "test block was available."
                ),
                evidence=[
                    "Action requested extend_existing_test",
                    "No valid ExistingTestContext survived parser integrity checks",
                ],
                risk="medium",
                fallback="Append a new test in the selected spec instead of editing an unsafe range.",
            ),
        )

    def _validate_patch_plan(
        self,
        request: GenerationRequest,
        patches: PatchSet,
        existing_test_context: ExistingTestContext | None,
        anchor_flow_context: AnchorFlowContext | None,
        flow_plan: Any | None,
        ownership: Any | None,
        requires_bootstrap: bool,
        attempt: int,
        policy: RepositoryPolicy | None = None,
    ) -> ValidationResult:
        stage = "patch_plan_guard" if attempt == 0 else "repair_patch_plan_guard"
        return self._run_stage(
            request.job_id,
            stage,
            lambda: self._patch_plan_check(
                patches,
                existing_test_context,
                anchor_flow_context,
                flow_plan,
                ownership,
                request.repo_path,
                requires_bootstrap,
                policy,
            ),
            started={"attempt": attempt},
            completed=lambda result: {
                "attempt": attempt,
                "passed": result.passed,
                "failed_checks": [
                    check.name for check in result.checks if not check.passed
                ],
            },
        )

    def _patch_plan_check(
        self,
        patches: PatchSet,
        existing_test_context: ExistingTestContext | None,
        anchor_flow_context: AnchorFlowContext | None,
        flow_plan: Any | None,
        ownership: Any | None = None,
        repo_path: str = "",
        requires_bootstrap: bool = False,
        policy: RepositoryPolicy | None = None,
    ) -> ValidationResult:
        self._bind_append_to_anchor_describe(patches, anchor_flow_context, repo_path)
        self._bind_extension_target(patches, existing_test_context, repo_path)
        checks = [
            self._extension_patch_check(patches, existing_test_context, flow_plan),
            self._append_integration_check(patches, repo_path, anchor_flow_context),
            self._append_reuse_check(patches, anchor_flow_context),
            self._reference_integrity_check(patches, repo_path),
            self._ownership_emission_check(patches, ownership),
            self._created_spec_structure_check(patches),
            self._bootstrap_scaffold_check(patches, requires_bootstrap),
        ]
        if policy is not None:
            checks.extend(self.policy.checks(patches, policy))
        append_reuse = next(
            (check for check in checks if check.name == "append_flow_reuse"), None
        )
        if append_reuse is not None and (
            "warning" in append_reuse.output.lower()
            or not append_reuse.passed
        ):
            logger.warning(
                "[playwright-generation] stage=append_flow_reuse status=advisory "
                "blocking=false target_spec=%s anchor=%s reason=%s",
                anchor_flow_context.file_path if anchor_flow_context else "none",
                anchor_flow_context.anchor_test_title if anchor_flow_context else "none",
                append_reuse.output,
            )
        blocking_checks = [
            check for check in checks if check.name != "append_flow_reuse"
        ]
        return ValidationResult(
            passed=all(check.passed for check in blocking_checks),
            checks=checks,
        )

    def _append_integration_check(
        self,
        patches: PatchSet,
        repo_path: str,
        anchor: AnchorFlowContext | None = None,
    ) -> ValidationCheck:
        append_patches = [
            patch
            for patch in patches.patches
            if patch.operation in {"append", "append_test"}
            and (anchor is None or patch.path == anchor.file_path)
            and patch.path.endswith((".spec.ts", ".spec.tsx", ".test.ts", ".test.tsx", ".e2e.ts", ".e2e.tsx"))
        ]
        if not append_patches:
            return ValidationCheck(
                name="append_integration",
                passed=True,
                output="No append patch requires integration validation.",
            )
        if len(append_patches) != 1:
            return ValidationCheck(
                name="append_integration",
                passed=False,
                output="Generation must contain exactly one append patch.",
            )

        patch = append_patches[0]
        path = Path(repo_path) / patch.path
        if not path.is_file():
            return ValidationCheck(
                name="append_integration",
                passed=False,
                output=f"Append target does not exist: {patch.path}",
            )

        parser = PlaywrightParserTool()
        existing = parser.extract_tests(patch.path, path.read_text(encoding="utf-8"))
        generated = parser.extract_tests(patch.path, patch.content)
        findings: list[str] = []
        if len(generated) != 1:
            findings.append("Append content must contain exactly one complete test block.")
        elif generated[0].test_title in {test.test_title for test in existing}:
            findings.append(
                f"Test title '{generated[0].test_title}' already exists in {patch.path}; "
                "rename only the generated test and preserve its behavior."
            )

        describes = parser.extract_describes(
            patch.path,
            path.read_text(encoding="utf-8"),
        )
        if patch.operation == "append_test":
            matching_describes = [
                block
                for block in describes
                if block.title == patch.target_describe_title
            ]
            if len(matching_describes) != 1:
                findings.append(
                    "append_test must identify exactly one target describe block."
                )
        elif patch.start_line is None and len(describes) != 1:
            findings.append(
                "Append target must have exactly one describe block when start_line is omitted."
            )
        elif patch.start_line is not None and not any(
            block.start_line < patch.start_line <= block.end_line for block in describes
        ):
            findings.append("Append start_line must select a describe block in the target file.")

        return ValidationCheck(
            name="append_integration",
            passed=not findings,
            output="\n".join(findings)
            if findings
            else f"Generated test is unique and targets a describe block in {patch.path}.",
        )

    def _bind_append_to_anchor_describe(
        self,
        patches: PatchSet,
        anchor: AnchorFlowContext | None,
        repo_path: str,
    ) -> None:
        if anchor is None:
            return
        append_patches = [
            patch
            for patch in patches.patches
            if patch.operation in {"append", "append_test"} and patch.path == anchor.file_path
        ]
        if len(append_patches) != 1:
            return
        patch = append_patches[0]
        patch.operation = "append_test"
        patch.target_describe_title = anchor.describe_title
        patch.start_line = None
        path = Path(repo_path) / patch.path
        if not path.is_file():
            return
        describes = PlaywrightParserTool().extract_describes(
            patch.path,
            path.read_text(encoding="utf-8", errors="ignore"),
        )
        matching = [block for block in describes if block.title == anchor.describe_title]
        if len(matching) != 1:
            return

    def _bind_extension_target(
        self,
        patches: PatchSet,
        context: ExistingTestContext | None,
        repo_path: str,
    ) -> None:
        if context is None:
            return
        matching = [
            patch
            for patch in patches.patches
            if patch.path == context.file_path
            and patch.operation in {"replace", "replace_test"}
        ]
        if len(matching) != 1:
            return
        patch = matching[0]
        target = Path(repo_path) / context.file_path
        if not target.is_file():
            return
        _, _, source = PlaywrightParserTool().find_test_block(
            context.file_path,
            target.read_text(encoding="utf-8", errors="ignore"),
            context.test_title,
            context.describe_title,
        )
        patch.operation = "replace_test"
        patch.start_line = None
        patch.end_line = None
        patch.target_test_title = context.test_title
        patch.target_describe_title = context.describe_title
        patch.expected_source = source

    def _extension_patch_check(
        self,
        patches: PatchSet,
        existing_test_context: ExistingTestContext | None,
        flow_plan: Any | None = None,
    ) -> ValidationCheck:
        if existing_test_context is None:
            return ValidationCheck(
                name="existing_test_extension_target",
                passed=True,
                output="No existing test extension target required.",
            )

        matching_patches = [
            patch for patch in patches.patches if patch.path == existing_test_context.file_path
        ]
        findings: list[str] = []
        if not matching_patches:
            findings.append(
                "extend_existing_test must structurally replace the selected test in "
                f"{existing_test_context.file_path}"
            )
        exact_replacements = [
            patch
            for patch in matching_patches
            if patch.operation == "replace_test"
            and patch.target_test_title == existing_test_context.test_title
            and patch.target_describe_title == existing_test_context.describe_title
            and bool(patch.expected_source)
        ]
        if matching_patches and not exact_replacements:
            findings.append(
                "extend_existing_test requires replace_test bound to the selected "
                f"describe/title in {existing_test_context.file_path}; generated targets were "
                f"{[(patch.operation, patch.target_describe_title, patch.target_test_title) for patch in matching_patches]}"
            )
        for patch in exact_replacements:
            if existing_test_context.test_title not in patch.content:
                findings.append(
                    "replacement content must preserve selected test title "
                    f"`{existing_test_context.test_title}`"
                )
            if "test(" not in patch.content and "test." not in patch.content:
                findings.append("replacement content must include a full Playwright test block")
            findings.extend(
                self._dropped_preserved_steps(existing_test_context, flow_plan, patch.content)
            )

        return ValidationCheck(
            name="existing_test_extension_target",
            passed=not findings,
            output="\n".join(findings)
            if findings
            else (
                "Existing test extension patch is structurally bound to: "
                f"{existing_test_context.file_path} :: "
                f"{existing_test_context.describe_title or '<root>'} :: "
                f"{existing_test_context.test_title}"
            ),
        )

    def _dropped_preserved_steps(
        self,
        existing_test_context: ExistingTestContext,
        flow_plan: Any | None,
        content: str,
    ) -> list[str]:
        """Return findings for proven steps the flow plan preserves but the patch drops.

        Only enforced for steps that both (a) the flow plan lists as preserved and
        (b) actually appear in the existing test source, so paraphrased or invented
        steps never cause a false failure.
        """
        preserved_steps = getattr(flow_plan, "preserved_steps", None) or []
        source = existing_test_context.source_excerpt or ""
        findings: list[str] = []
        for step in preserved_steps:
            step_text = step.strip()
            if not step_text or step_text not in source:
                continue
            if step_text not in content:
                findings.append(
                    "extend_existing_test must retain the proven preserved step "
                    f"`{step_text}`"
                )
        return findings

    def _append_reuse_check(
        self,
        patches: PatchSet,
        anchor_flow_context: AnchorFlowContext | None,
    ) -> ValidationCheck:
        if anchor_flow_context is None:
            return ValidationCheck(
                name="append_flow_reuse",
                passed=True,
                output="No anchor flow reuse target required.",
            )

        generic_fixtures = {"page", "request", "context", "browser"}
        reusable_signals = [
            *anchor_flow_context.page_objects,
            *[
                fixture
                for fixture in anchor_flow_context.fixtures
                if fixture not in generic_fixtures
            ],
        ]
        matching_patches = [
            patch for patch in patches.patches if patch.path == anchor_flow_context.file_path
        ]
        if not matching_patches:
            return ValidationCheck(
                name="append_flow_reuse",
                passed=True,
                output=(
                    "No patch targets the anchor spec; append reuse not evaluated here."
                ),
            )

        combined_content = "\n".join(patch.content for patch in matching_patches)
        anchor_marker = f"// Anchor flow: {anchor_flow_context.anchor_test_title}"
        end_marker = "// End anchor flow; new scenario steps begin below."
        if anchor_marker not in combined_content or end_marker not in combined_content:
            return ValidationCheck(
                name="append_flow_reuse",
                passed=True,
                output=(
                    "Non-blocking anchor reuse warning: append_new_test should identify the anchor with "
                    f"`{anchor_marker}` and mark its reuse boundary with `{end_marker}`."
                ),
            )
        anchor_lines = [
            " ".join(line.strip().split())
            for line in (anchor_flow_context.source_excerpt or "").splitlines()[1:-1]
            if line.strip()
        ]
        generated_lines = [
            " ".join(line.strip().split())
            for line in combined_content.splitlines()
            if line.strip()
        ]
        anchor_start = next(
            (
                index
                for index in range(len(generated_lines) - len(anchor_lines) + 1)
                if generated_lines[index : index + len(anchor_lines)] == anchor_lines
            ),
            None,
        ) if anchor_lines else None
        if anchor_lines and anchor_start is None:
            return ValidationCheck(
                name="append_flow_reuse",
                passed=True,
                output=(
                    "Non-blocking anchor reuse warning: append_new_test should preserve the anchor's inner flow as one "
                    "uninterrupted block before adding the new scenario steps."
                ),
            )
        marker_line = generated_lines.index(anchor_marker)
        end_marker_line = generated_lines.index(end_marker)
        if marker_line > end_marker_line:
            return ValidationCheck(
                name="append_flow_reuse",
                passed=True,
                output="Non-blocking anchor reuse warning: anchor flow markers are out of order.",
            )
        if anchor_start is not None and not (
            marker_line < anchor_start
            and anchor_start + len(anchor_lines) <= end_marker_line
        ):
            return ValidationCheck(
                name="append_flow_reuse",
                passed=True,
                output="Non-blocking anchor reuse warning: anchor comments should surround the preserved flow block.",
            )
        if not reusable_signals:
            return ValidationCheck(
                name="append_flow_reuse",
                passed=True,
                output="Appended test preserves the anchor flow as an uninterrupted block.",
            )
        reused = [signal for signal in reusable_signals if signal in combined_content]
        return ValidationCheck(
            name="append_flow_reuse",
            passed=True,
            output=(
                f"Appended test reuses anchor setup signals: {reused}"
                if reused
                else (
                    "Non-blocking anchor reuse warning: append_new_test should reuse "
                    "the anchor flow's proven setup; the "
                    "generated test references none of its page objects or non-generic "
                    f"fixtures {reusable_signals} and appears to reinvent the flow."
                )
            ),
        )

    def _reference_integrity_check(
        self,
        patches: PatchSet,
        repo_path: str,
    ) -> ValidationCheck:
        """Verify generated code references only things that exist.

        Two conservative checks over generated TS/TSX patches:
        1. Every relative import must resolve to a repository file or to another
           patch in the same set.
        2. Every method called on a locally-instantiated page object
           (``const po = new XxxPage(...)`` then ``po.method(...)``) must exist in
           the class's source file (resolved through the patch's own import), or in
           a patch that creates/modifies that file.

        Anything that cannot be resolved (aliased tsconfig paths, inherited classes,
        dynamic patterns) is skipped rather than failed, so the check never blocks on
        ambiguity — it only fails on provably invented references.
        """
        findings: list[str] = []
        patch_contents = {patch.path: patch.content for patch in patches.patches}
        for patch in patches.patches:
            if not patch.path.endswith((".ts", ".tsx", ".js", ".jsx")):
                continue
            import_map = self._resolve_patch_imports(
                patch, repo_path, patch_contents, findings
            )
            self._check_page_object_members(patch, import_map, findings)

        return ValidationCheck(
            name="reference_integrity",
            passed=not findings,
            output="\n".join(findings)
            if findings
            else "All resolvable imports and page-object member references exist.",
        )

    def _resolve_patch_imports(
        self,
        patch: Any,
        repo_path: str,
        patch_contents: dict[str, str],
        findings: list[str],
    ) -> dict[str, str]:
        """Resolve the patch's relative imports to file contents.

        Returns a map of imported symbol name -> source file content. Records a
        finding for any relative import that resolves to nothing. Non-relative
        (package/tsconfig-alias) imports are skipped.
        """
        import_map: dict[str, str] = {}
        root = Path(repo_path) if repo_path else None
        repo_available = root is not None and root.exists()
        pattern = re.compile(
            r"import\s+(?:\{(?P<named>[^}]+)\}|(?P<default>\w+))\s+from\s+['\"](?P<path>\.[^'\"]+)['\"]"
        )
        for match in pattern.finditer(patch.content):
            import_path = match.group("path")
            base = PurePosixPath(patch.path).parent
            normalized = PurePosixPath(
                posixpath.normpath(str(base / import_path))
            ).as_posix()
            candidates = [
                f"{normalized}{suffix}"
                for suffix in (".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "")
            ]
            content: str | None = None
            for candidate in candidates:
                if candidate in patch_contents and candidate != patch.path:
                    content = patch_contents[candidate]
                    break
                if repo_available:
                    target = root / candidate
                    if target.is_file():
                        content = target.read_text(encoding="utf-8", errors="ignore")
                        break
            if content is None:
                if repo_available:
                    findings.append(
                        f"{patch.path}: import '{import_path}' does not resolve to a "
                        "repository file or a generated patch"
                    )
                continue
            symbols = (
                [
                    part.strip().split(" as ")[-1].strip()
                    for part in match.group("named").split(",")
                    if part.strip()
                ]
                if match.group("named")
                else [match.group("default")]
            )
            for symbol in symbols:
                if symbol:
                    import_map[symbol] = content
        return import_map

    def _check_page_object_members(
        self,
        patch: Any,
        import_map: dict[str, str],
        findings: list[str],
    ) -> None:
        instantiations = re.finditer(
            r"(?:const|let|var)\s+(?P<var>\w+)\s*=\s*(?:await\s+)?new\s+(?P<cls>[A-Z]\w*)\s*\(",
            patch.content,
        )
        for instantiation in instantiations:
            variable = instantiation.group("var")
            class_name = instantiation.group("cls")
            class_source = import_map.get(class_name)
            if class_source is None:
                continue  # class not resolvable from this patch's imports; skip
            if re.search(r"\bextends\b", class_source):
                continue  # inherited members are not cheaply resolvable; skip
            for call in re.finditer(rf"\b{re.escape(variable)}\.(\w+)\s*\(", patch.content):
                member = call.group(1)
                if not re.search(rf"\b{re.escape(member)}\b", class_source):
                    findings.append(
                        f"{patch.path}: `{variable}.{member}()` references a member "
                        f"that does not exist in `{class_name}`"
                    )

    def _ownership_emission_check(
        self,
        patches: PatchSet,
        ownership: Any | None,
    ) -> ValidationCheck:
        if (
            ownership is None
            or not getattr(ownership, "create_new", False)
            or getattr(ownership, "owner_kind", "spec") == "spec"
        ):
            return ValidationCheck(
                name="ownership_emission",
                passed=True,
                output="No new non-spec owner promised by ownership resolution.",
            )
        owner_path = getattr(ownership, "owner_path", "")
        if any(patch.path == owner_path for patch in patches.patches):
            return ValidationCheck(
                name="ownership_emission",
                passed=True,
                output=f"Patch set creates the promised owner at {owner_path}.",
            )
        return ValidationCheck(
            name="ownership_emission",
            passed=False,
            output=(
                f"Ownership resolution promised a new {ownership.owner_kind} at "
                f"{owner_path}; the patch set must create it instead of inlining "
                "locators or helpers into the spec."
            ),
        )

    def _created_spec_structure_check(self, patches: PatchSet) -> ValidationCheck:
        spec_suffixes = (".spec.ts", ".spec.tsx", ".e2e.ts", ".e2e.tsx", ".pw.ts", ".playwright.ts")
        findings: list[str] = []
        for patch in patches.patches:
            if patch.operation != "create" or not patch.path.endswith(spec_suffixes):
                continue
            if "@playwright/test" not in patch.content:
                findings.append(
                    f"{patch.path}: created spec must import from '@playwright/test'"
                )
            if "test(" not in patch.content and "test." not in patch.content:
                findings.append(f"{patch.path}: created spec must declare a test block")
            if "expect(" not in patch.content:
                findings.append(f"{patch.path}: created spec must assert with expect()")
        return ValidationCheck(
            name="created_spec_structure",
            passed=not findings,
            output="\n".join(findings)
            if findings
            else "Created spec files follow Playwright structure.",
        )

    def _bootstrap_scaffold_check(
        self,
        patches: PatchSet,
        requires_bootstrap: bool,
    ) -> ValidationCheck:
        """Ensure the framework scaffold survives critic review and repair.

        The scaffold patches are added deterministically, but later LLM passes
        return whole patch sets and could drop them; a bootstrap repo without its
        config and dependency would produce an unrunnable suite.
        """
        if not requires_bootstrap:
            return ValidationCheck(
                name="bootstrap_scaffold",
                passed=True,
                output="Repository does not require framework bootstrap.",
            )
        findings: list[str] = []
        has_config = any(
            patch.path.startswith("playwright.config.") for patch in patches.patches
        )
        if not has_config:
            findings.append("bootstrap requires a playwright.config.* patch")
        package_patches = [
            patch for patch in patches.patches if patch.path == "package.json"
        ]
        if not package_patches:
            findings.append("bootstrap requires a package.json patch")
        elif not any("@playwright/test" in patch.content for patch in package_patches):
            findings.append(
                "package.json patch must add the @playwright/test devDependency"
            )
        return ValidationCheck(
            name="bootstrap_scaffold",
            passed=not findings,
            output="\n".join(findings)
            if findings
            else "Bootstrap scaffold (config + dependency) present in patch set.",
        )

    def _repair_patch_plan(
        self,
        request: GenerationRequest,
        patches: PatchSet,
        validation: ValidationResult,
        ui_context: PlaywrightUiContext,
        existing_test_context: ExistingTestContext | None,
        critic: CriticAgent,
        repair: RepairAgent,
        max_attempts: int,
        anchor_flow_context: AnchorFlowContext | None = None,
        flow_plan: Any | None = None,
        ownership_resolution: Any | None = None,
        locator_decisions: Any | None = None,
        requires_bootstrap: bool = False,
        policy: RepositoryPolicy | None = None,
        budget: GenerationBudget | None = None,
    ) -> tuple[PatchSet, ValidationResult | None]:
        for attempt in range(1, max_attempts + 1):
            if budget is not None:
                budget.charge_repair_attempt()
            logger.log(logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", 'repair_loop', 'plan_failed', {'job_id': request.job_id, 'attempt': attempt, 'max_attempts': max_attempts, 'failed_checks': [check.name for check in validation.checks if not check.passed]})
            repaired_patches = self._run_stage(
                request.job_id,
                "repair_generation",
                lambda current=patches, failed=validation: repair.repair(
                    current, failed, anchor_flow_context, locator_decisions
                ),
                started={"attempt": attempt, "reason": "patch_plan_guard"},
                completed=lambda patch_set: {
                    "attempt": attempt,
                    "patches": len(patch_set.patches),
                    "paths": [patch.path for patch in patch_set.patches],
                },
            )
            patches = self._run_stage(
                request.job_id,
                "repair_critic_review",
                lambda current=repaired_patches: critic.review(
                    current, ui_context, anchor_flow_context, locator_decisions
                ),
                started={"attempt": attempt, "reason": "patch_plan_guard"},
                completed=lambda reviewed: {
                    "attempt": attempt,
                    "patches": len(reviewed.patches),
                },
            )
            validation = self._validate_patch_plan(
                request,
                patches,
                existing_test_context,
                anchor_flow_context,
                flow_plan,
                ownership_resolution,
                requires_bootstrap,
                attempt=attempt,
                policy=policy,
            )
            validation.repair_attempted = True
            if validation.passed:
                logger.log(logging.INFO, "[playwright-generation] stage=%s | status=%s | details=%s", 'repair_loop', 'plan_completed', {'job_id': request.job_id, 'attempts': attempt, 'passed': True})
                return patches, validation

        logger.log(logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", 'repair_loop', 'plan_exhausted', {'job_id': request.job_id, 'attempts': max_attempts, 'passed': False})
        validation.repair_attempted = max_attempts > 0
        return patches, validation

    def _write_patches(
        self,
        request: GenerationRequest,
        patches: PatchSet,
        attempt: int,
        workspace: JobWorkspace | None = None,
    ) -> PatchWriteResult:
        stage = "patch_write" if attempt == 0 else "repair_patch_write"

        def write() -> PatchWriteResult:
            if workspace is not None:
                self.workspaces.snapshot_targets(workspace, patches)
            result = self.adapter.apply_patch(request.repo_path, patches)
            if workspace is not None:
                self.workspaces.record_patches(workspace, result)
            return result

        return self._run_stage(
            request.job_id,
            stage,
            write,
            started={"attempt": attempt},
            completed=lambda result: {
                "attempt": attempt,
                "applied": len(result.applied),
                "paths": [patch.path for patch in result.applied],
            },
        )

    def _rollback_patches(
        self,
        request: GenerationRequest,
        result: PatchWriteResult,
        workspace: JobWorkspace | None = None,
    ) -> None:
        self.adapter.rollback(request.repo_path, result)
        if workspace is not None:
            self.workspaces.record_rollback(workspace, result)

    def _validate_patches(
        self,
        request: GenerationRequest,
        patches: PatchSet,
        ui_context: PlaywrightUiContext,
        attempt: int,
    ) -> ValidationResult:
        stage = "validation" if attempt == 0 else "repair_validation"
        return self._run_stage(
            request.job_id,
            stage,
            lambda: self.adapter.validate(request.repo_path, patches, ui_context),
            started={"attempt": attempt},
            completed=lambda result: {
                "attempt": attempt,
                "passed": result.passed,
                "checks": len(result.checks),
                "failed_checks": [
                    check.name for check in result.checks if not check.passed
                ],
            },
        )
