from __future__ import annotations

import logging
import posixpath
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Any

from app.agents.critic_agent import CriticAgent
from app.agents.functional_intent_agent import FunctionalIntentAgent
from app.agents.locator_reasoning_agent import LocatorReasoningAgent
from app.agents.repair_agent import RepairAgent
from app.config import settings
from app.coverage.coverage_preservation_service import CoveragePreservationService
from app.errors import UnsupportedRepositoryError
from app.patching.scoped_patch_writer import ScopedPatchWriter
from app.schemas.behavioral_test_unit import (
    AnchorFlowContext,
    BehavioralTestUnit,
    ExistingTestContext,
)
from app.schemas.code_patch import PatchSet, PatchWriteResult
from app.runtime.generation_runtime import GenerationRuntime
from app.schemas.decision_trace import DecisionTrace
from app.schemas.generation_request import GenerationRequest
from app.schemas.generation_result import GenerationResult
from app.schemas.playwright_ui_context import PlaywrightUiContext
from app.schemas.test_action_decision import TestActionDecision, TestActions
from app.services.behavioral_inventory_service import BehavioralInventoryService
from app.services.bootstrap_scaffold_service import BootstrapScaffoldService
from app.services.code_generation_service import CodeGenerationService
from app.services.flow_merge_service import FlowMergeService
from app.services.inventory_service import InventoryService
from app.services.ownership_resolution_service import OwnershipResolutionService
from app.services.playwright_ui_intelligence_service import PlaywrightUiIntelligenceService
from app.services.repo_strategy_service import RepoStrategyService
from app.services.result_builder_service import ResultBuilderService
from app.services.review_report_service import ReviewReportService
from app.services.source_intelligence_service import SourceIntelligenceService
from app.services.spec_placement_service import SpecPlacementService
from app.services.technology_intelligence_service import TechnologyIntelligenceService
from app.services.test_action_service import TestActionService
from app.services.test_file_classifier_service import TestFileClassifierService
from app.services.test_value_service import TestValueService
from app.services.traceability_service import TraceabilityService
from app.schemas.validation_result import ValidationCheck, ValidationResult
from app.validation.repo_command_validator import RepoCommandValidator
from app.logging_config import log_event

logger = logging.getLogger(__name__)


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
        self.bootstrap = BootstrapScaffoldService()
        self.patch_writer = ScopedPatchWriter()
        self.validator = RepoCommandValidator()
        self.results = ResultBuilderService()
        self.coverage = CoveragePreservationService()
        self.test_value = TestValueService()
        self.traceability = TraceabilityService()
        self.review_report = ReviewReportService()

    def generate(self, request: GenerationRequest) -> GenerationResult:
        context = {"job_id": request.job_id, "repo_path": request.repo_path, "stage": "generation"}
        generation_started_at = perf_counter()
        review_reasons: list[str] = []
        log_event(
            logger,
            logging.INFO,
            "generation",
            "started",
            job_id=request.job_id,
            repo=request.repo_path,
        )
        try:
            repo_profile = self._run_stage(
                request.job_id,
                "repo_strategy",
                lambda: self.repo_strategy.detect(request.repo_path, request.branch),
                started={"repo": request.repo_path, "branch": request.branch or "default"},
                completed=lambda profile: {"support_status": profile.support_status},
            )
            if repo_profile.support_status == "unsupported":
                self._log_stage(request.job_id, "repo_strategy", "failed", "unsupported_repository")
                raise UnsupportedRepositoryError(repo_profile)

            runtime = self._run_stage(
                request.job_id,
                "runtime",
                lambda: GenerationRuntime.from_request(request, db=self.db),
                started={"action": "creating_llm_client"},
            )
            functional_intent = FunctionalIntentAgent(llm_client=runtime.llm_client)
            source_intelligence = SourceIntelligenceService(llm_client=runtime.llm_client)
            spec_placement = SpecPlacementService(llm_client=runtime.llm_client)
            test_action = TestActionService(llm_client=runtime.llm_client)
            flow_merge = FlowMergeService(llm_client=runtime.llm_client)
            ownership = OwnershipResolutionService(llm_client=runtime.llm_client)
            locators = LocatorReasoningAgent(llm_client=runtime.llm_client)
            code_generation = CodeGenerationService(llm_client=runtime.llm_client)
            critic = CriticAgent(llm_client=runtime.llm_client)
            repair = RepairAgent(llm_client=runtime.llm_client)

            self._run_stage(
                request.job_id,
                "technology_intelligence",
                lambda: self.technology.detect(repo_profile),
            )

            classifications = self._run_stage(
                request.job_id,
                "test_file_classification",
                lambda: self.classifier.classify(request.repo_path),
                completed=lambda files: {"classified_files": len(files)},
            )

            inventory = self._run_stage(
                request.job_id,
                "repository_inventory",
                lambda: self.inventory.build(request.repo_path, classifications),
                completed=lambda built: {
                    "test_files": len(built.test_files),
                    "page_objects": len(built.page_objects),
                },
            )

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
                lambda: self.behavioral_inventory.extract(inventory),
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

            action = self._run_stage(
                request.job_id,
                "test_action_decision",
                lambda: test_action.decide(placement, behavior, intent, ui_context, request.repo_path),
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
                lambda: self._resolve_existing_test_context(placement, action, behavior),
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
                lambda: self._resolve_anchor_flow_context(placement, action, behavior),
                completed=lambda anchor: {
                    "selected": anchor is not None,
                    "file": anchor.file_path if anchor else "none",
                    "anchor_test": anchor.anchor_test_title if anchor else "none",
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
                log_event(
                    logger,
                    logging.INFO,
                    "flow_merge",
                    "skipped",
                    action=action.action,
                    reason="flow_merge_only_applies_to_extension",
                )
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
                lambda: locators.decide(source),
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
                lambda: critic.review(patches, ui_context),
                completed=lambda reviewed: {"patches": len(reviewed.patches)},
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

            test_value_report = self._run_optional_stage(
                request.job_id,
                "test_value_analysis",
                lambda: self.test_value.evaluate(patches, behavior),
            )
            if test_value_report is not None:
                review_reasons.extend(self.test_value.review_reasons(test_value_report))

            patch_result, validation, patches = self._write_validate_and_repair(
                request=request,
                patches=patches,
                ui_context=ui_context,
                existing_test_context=existing_test_context,
                anchor_flow_context=anchor_flow_context,
                flow_plan=flow_plan,
                ownership_resolution=ownership_resolution,
                requires_bootstrap=repo_profile.requires_bootstrap,
                critic=critic,
                repair=repair,
            )

            coverage_report = self._assess_coverage_preservation(
                request, patches, patch_result, behavior, review_reasons
            )

            traceability_matrix = self._run_optional_stage(
                request.job_id,
                "requirement_traceability",
                lambda: self.traceability.build(request, intent, patches, behavior),
            )
            if traceability_matrix is not None:
                review_reasons.extend(
                    self.traceability.review_reasons(traceability_matrix)
                )

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
            )

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
                ),
                completed=lambda built: {
                    "files_changed": len(built.files_changed),
                    "confidence": built.confidence,
                    "needs_review": built.needs_review,
                },
            )
            log_event(
                logger,
                logging.INFO,
                "generation",
                "completed",
                job_id=request.job_id,
                duration_ms=round((perf_counter() - generation_started_at) * 1000, 2),
                files_changed=len(result.files_changed),
                confidence=result.confidence,
            )
            return result
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "generation",
                "failed",
                job_id=request.job_id,
                duration_ms=round((perf_counter() - generation_started_at) * 1000, 2),
                error=exc,
            )
            logger.exception(
                "[playwright-generation] job_id=%s stage=generation status=failed context=%s error=%s",
                request.job_id,
                context,
                exc,
            )
            raise

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
            log_event(
                logger,
                logging.INFO,
                "coverage_preservation",
                "skipped",
                job_id=request.job_id,
                reason="no_patches_applied",
            )
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
        log_event(logger, logging.INFO, stage, "started", job_id=job_id, advisory=True)
        started_at = perf_counter()
        try:
            action()
            log_event(
                logger,
                logging.INFO,
                stage,
                "completed",
                job_id=job_id,
                advisory=True,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
            )
        except Exception as exc:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            log_event(
                logger,
                logging.WARNING,
                stage,
                "failed",
                job_id=job_id,
                advisory=True,
                duration_ms=duration_ms,
                error=exc,
            )
            logger.exception(
                "[playwright-generation] job_id=%s stage=%s status=failed advisory=true error=%s",
                job_id,
                stage,
                exc,
            )

    def _run_optional_stage(self, job_id: str, stage: str, action: Callable[[], Any]) -> Any | None:
        """Run a best-effort stage whose result improves generation but is not required.

        Returns the stage result on success, or ``None`` if it fails, so a failure in
        an advisory-quality signal never aborts the overall generation.
        """
        log_event(logger, logging.INFO, stage, "started", job_id=job_id, optional=True)
        started_at = perf_counter()
        try:
            result = action()
            log_event(
                logger,
                logging.INFO,
                stage,
                "completed",
                job_id=job_id,
                optional=True,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
            )
            return result
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                stage,
                "failed",
                job_id=job_id,
                optional=True,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
                error=exc,
            )
            logger.exception(
                "[playwright-generation] job_id=%s stage=%s status=failed optional=true error=%s",
                job_id,
                stage,
                exc,
            )
            return None

    def _log_stage(
        self,
        job_id: str,
        stage: str,
        status: str,
        detail: str | None = None,
    ) -> None:
        message = (
            f"[playwright-generation] job_id={job_id} stage={stage} status={status}"
        )
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
        started_details = {"job_id": job_id, **(started or {})}
        log_event(logger, logging.INFO, stage, "started", **started_details)
        started_at = perf_counter()
        try:
            result = action()
        except Exception as exc:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            log_event(
                logger,
                logging.ERROR,
                stage,
                "failed",
                job_id=job_id,
                duration_ms=duration_ms,
                error=exc,
            )
            raise

        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        completed_details = completed(result) if completed else {}
        log_event(
            logger,
            logging.INFO,
            stage,
            "completed",
            job_id=job_id,
            duration_ms=duration_ms,
            **completed_details,
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
        requires_bootstrap: bool = False,
    ) -> tuple[PatchWriteResult, ValidationResult | None, PatchSet]:
        patch_result = PatchWriteResult()
        max_attempts = max(settings.max_repair_attempts, 0)
        plan_validation = self._validate_patch_plan(
            request,
            patches,
            existing_test_context,
            anchor_flow_context,
            flow_plan,
            ownership_resolution,
            requires_bootstrap,
            attempt=0,
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
                requires_bootstrap=requires_bootstrap,
                critic=critic,
                repair=repair,
                max_attempts=max_attempts,
            )
            if validation is not None and not validation.passed:
                return patch_result, validation, patches

        patch_result = self._write_patches(request, patches, attempt=0)

        if not request.run_validation:
            self._log_stage(request.job_id, "validation", "skipped")
            return patch_result, None, patches

        validation = self._validate_patches(request, patches, ui_context, attempt=0)
        if validation.passed:
            return patch_result, validation, patches

        for attempt in range(1, max_attempts + 1):
            log_event(
                logger,
                logging.WARNING,
                "repair_loop",
                "validation_failed",
                job_id=request.job_id,
                attempt=attempt,
                max_attempts=max_attempts,
                failed_checks=[
                    check.name for check in validation.checks if not check.passed
                ],
            )
            self._run_stage(
                request.job_id,
                "patch_rollback",
                lambda result=patch_result: self.patch_writer.rollback(
                    request.repo_path,
                    result,
                ),
                started={"attempt": attempt},
            )
            repaired_patches = self._run_stage(
                request.job_id,
                "repair_generation",
                lambda current=patches, failed=validation: repair.repair(current, failed),
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
                lambda current=repaired_patches: critic.review(current, ui_context),
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
            )
            if not plan_validation.passed:
                validation = plan_validation
                continue
            patch_result = self._write_patches(request, patches, attempt=attempt)
            validation = self._validate_patches(request, patches, ui_context, attempt=attempt)
            validation.repair_attempted = True
            if validation.passed:
                log_event(
                    logger,
                    logging.INFO,
                    "repair_loop",
                    "completed",
                    job_id=request.job_id,
                    attempts=attempt,
                    passed=True,
                )
                return patch_result, validation, patches

        log_event(
            logger,
            logging.WARNING,
            "repair_loop",
            "exhausted",
            job_id=request.job_id,
            attempts=max_attempts,
            passed=False,
        )
        validation.repair_attempted = max_attempts > 0
        return patch_result, validation, patches

    def _resolve_existing_test_context(
        self,
        placement: Any,
        action: Any,
        candidates: list[BehavioralTestUnit],
    ) -> ExistingTestContext | None:
        if action.action != TestActions.EXTEND_EXISTING_TEST:
            log_event(
                logger,
                logging.INFO,
                "existing_test_context",
                "skipped",
                action=action.action,
            )
            return None

        target_spec = placement.target_spec_file
        target_title = action.target_test_title
        matches = [
            candidate
            for candidate in candidates
            if candidate.test_title == target_title
            and (not target_spec or candidate.file_path == target_spec)
        ]
        if not matches and target_title:
            matches = [
                candidate for candidate in candidates if candidate.test_title == target_title
            ]
        if not matches and target_spec:
            matches = [candidate for candidate in candidates if candidate.file_path == target_spec]
        if not matches and candidates:
            matches = [candidates[0]]
        if not matches:
            log_event(
                logger,
                logging.WARNING,
                "existing_test_context",
                "missing",
                target_spec=target_spec or "none",
                target_test=target_title or "none",
            )
            return None

        selected = matches[0]
        if selected.test_title != target_title:
            log_event(
                logger,
                logging.WARNING,
                "existing_test_context",
                "fallback_selected",
                requested_title=target_title or "none",
                selected_title=selected.test_title,
                file=selected.file_path,
                lines=f"{selected.start_line}-{selected.end_line}",
            )
        else:
            log_event(
                logger,
                logging.INFO,
                "existing_test_context",
                "selected",
                file=selected.file_path,
                test_title=selected.test_title,
                lines=f"{selected.start_line}-{selected.end_line}",
            )

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

        log_event(
            logger,
            logging.INFO,
            "spec_placement",
            "bootstrap_normalized",
            from_target=placement.target_spec_file,
            to_target=normalized_target,
            from_create_new=placement.create_new,
        )
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
        log_event(
            logger,
            logging.WARNING,
            "spec_placement",
            "low_confidence_flagged",
            confidence=placement.confidence,
            threshold=threshold,
            target_spec=placement.target_spec_file,
        )

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
        log_event(
            logger,
            logging.WARNING,
            stage,
            "shallow_decision_trace",
            decision=decision or "empty",
            has_justification=bool(justification),
            evidence_count=len(evidence),
        )

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
        log_event(
            logger,
            logging.WARNING,
            "flow_merge",
            "low_confidence_flagged",
            confidence=flow_plan.confidence,
            threshold=threshold,
        )

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
        log_event(
            logger,
            logging.WARNING,
            "ownership_resolution",
            "low_confidence_flagged",
            confidence=ownership.confidence,
            threshold=threshold,
            owner_path=ownership.owner_path,
            create_new=ownership.create_new,
        )

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
            log_event(
                logger,
                logging.WARNING,
                "test_action_decision",
                "low_confidence_flagged",
                action=action.action,
                confidence=action.confidence,
                threshold=threshold,
            )
            return action

        capped_confidence = min(action.confidence, 0.35)
        log_event(
            logger,
            logging.WARNING,
            "test_action_decision",
            "low_confidence_downgraded",
            from_action=action.action,
            to_action=TestActions.APPEND_NEW_TEST,
            confidence=action.confidence,
            threshold=threshold,
        )
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
        log_event(
            logger,
            logging.WARNING,
            "test_action_decision",
            "reconciled_with_placement",
            from_action=action.action,
            to_action=coerced_action,
            placement_create_new=placement.create_new,
            target_spec=placement.target_spec_file,
        )
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
    ) -> AnchorFlowContext | None:
        """Pick a sibling test in the target spec to seed an appended test's flow.

        For ``append_new_test`` the new test should reuse the proven
        setup/auth/navigation/fixtures/page objects of an existing sibling in
        ``target_spec_file`` rather than reinvent them. For ``create_new_spec`` the
        richest test anywhere in the repository serves as a style/setup template for
        the new spec; when the repository has no candidates at all, generation falls
        back to the Playwright best-practices scaffold in the prompt. In both cases
        the anchor is the candidate with the richest reusable setup (most page
        objects + fixtures), tie-broken by the longest source excerpt and then
        earliest position, and it is a reference only — never patched.
        """
        if action.action == TestActions.APPEND_NEW_TEST:
            pool = [
                candidate
                for candidate in candidates
                if candidate.file_path == placement.target_spec_file
            ]
            pool_description = "sibling test(s) in the target spec"
            empty_reason = "no_sibling_in_target_spec"
        elif action.action == TestActions.CREATE_NEW_SPEC:
            pool = list(candidates)
            pool_description = "existing test(s) across the repository"
            empty_reason = "no_template_candidates_in_repository"
        else:
            log_event(
                logger,
                logging.INFO,
                "anchor_flow_context",
                "skipped",
                action=action.action,
            )
            return None

        if not pool:
            log_event(
                logger,
                logging.INFO,
                "anchor_flow_context",
                empty_reason,
                target_spec=placement.target_spec_file,
            )
            return None

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
        log_event(
            logger,
            logging.INFO,
            "anchor_flow_context",
            "selected",
            file=anchor.file_path,
            anchor_test=anchor.test_title,
            page_objects=len(anchor.page_objects),
            fixtures=len(anchor.fixtures),
            pool=len(pool),
        )
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

        log_event(
            logger,
            logging.WARNING,
            "existing_test_context",
            "downgraded_action",
            from_action=action.action,
            to_action="append_new_test",
            reason="no_valid_existing_test_context",
        )
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
    ) -> ValidationResult:
        checks = [
            self._extension_patch_check(patches, existing_test_context, flow_plan),
            self._append_reuse_check(patches, anchor_flow_context),
            self._reference_integrity_check(patches, repo_path),
            self._ownership_emission_check(patches, ownership),
            self._created_spec_structure_check(patches),
            self._bootstrap_scaffold_check(patches, requires_bootstrap),
        ]
        return ValidationResult(
            passed=all(check.passed for check in checks),
            checks=checks,
        )

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
                "extend_existing_test must patch "
                f"{existing_test_context.file_path} at lines "
                f"{existing_test_context.start_line}-{existing_test_context.end_line}"
            )
        exact_replacements = [
            patch
            for patch in matching_patches
            if patch.operation == "replace"
            and patch.start_line == existing_test_context.start_line
            and patch.end_line == existing_test_context.end_line
        ]
        if matching_patches and not exact_replacements:
            findings.append(
                "extend_existing_test requires an exact replace patch for "
                f"{existing_test_context.file_path}:{existing_test_context.start_line}-"
                f"{existing_test_context.end_line}; generated ranges were "
                f"{[(patch.operation, patch.start_line, patch.end_line) for patch in matching_patches]}"
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
                "Existing test extension patch targets the selected block exactly: "
                f"{existing_test_context.file_path}:"
                f"{existing_test_context.start_line}-{existing_test_context.end_line}"
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
        if not reusable_signals:
            return ValidationCheck(
                name="append_flow_reuse",
                passed=True,
                output="Anchor flow has no reusable page objects or non-generic fixtures.",
            )

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
        reused = [signal for signal in reusable_signals if signal in combined_content]
        passed = bool(reused)
        return ValidationCheck(
            name="append_flow_reuse",
            passed=passed,
            output=(
                f"Appended test reuses anchor setup signals: {reused}"
                if passed
                else (
                    "append_new_test must reuse the anchor flow's proven setup; the "
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
        requires_bootstrap: bool = False,
    ) -> tuple[PatchSet, ValidationResult | None]:
        for attempt in range(1, max_attempts + 1):
            log_event(
                logger,
                logging.WARNING,
                "repair_loop",
                "plan_failed",
                job_id=request.job_id,
                attempt=attempt,
                max_attempts=max_attempts,
                failed_checks=[
                    check.name for check in validation.checks if not check.passed
                ],
            )
            repaired_patches = self._run_stage(
                request.job_id,
                "repair_generation",
                lambda current=patches, failed=validation: repair.repair(current, failed),
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
                lambda current=repaired_patches: critic.review(current, ui_context),
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
            )
            validation.repair_attempted = True
            if validation.passed:
                log_event(
                    logger,
                    logging.INFO,
                    "repair_loop",
                    "plan_completed",
                    job_id=request.job_id,
                    attempts=attempt,
                    passed=True,
                )
                return patches, validation

        log_event(
            logger,
            logging.WARNING,
            "repair_loop",
            "plan_exhausted",
            job_id=request.job_id,
            attempts=max_attempts,
            passed=False,
        )
        validation.repair_attempted = max_attempts > 0
        return patches, validation

    def _write_patches(
        self,
        request: GenerationRequest,
        patches: PatchSet,
        attempt: int,
    ) -> PatchWriteResult:
        stage = "patch_write" if attempt == 0 else "repair_patch_write"
        return self._run_stage(
            request.job_id,
            stage,
            lambda: self.patch_writer.apply(request.repo_path, patches),
            started={"attempt": attempt},
            completed=lambda result: {
                "attempt": attempt,
                "applied": len(result.applied),
                "paths": [patch.path for patch in result.applied],
            },
        )

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
            lambda: self.validator.validate(request.repo_path, patches, ui_context),
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
