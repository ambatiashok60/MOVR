from __future__ import annotations



from worktop.test_agent.app.schemas.code_patch import PatchSet, PatchWriteResult
from worktop.test_agent.app.schemas.coverage import CoveragePreservationReport
from worktop.test_agent.app.schemas.decision_trace import DecisionTrace
from worktop.test_agent.app.schemas.generation_budget import BudgetReport
from worktop.test_agent.app.schemas.generation_manifest import GenerationManifest
from worktop.test_agent.app.schemas.generation_request import GenerationRequest
from worktop.test_agent.app.schemas.generation_result import GenerationResult
from worktop.test_agent.app.schemas.repo_profile import RepoProfile
from worktop.test_agent.app.schemas.review_report import ReviewReport
from worktop.test_agent.app.schemas.test_value import TestValueReport
from worktop.test_agent.app.schemas.traceability import TraceabilityMatrix
from worktop.test_agent.app.schemas.validation_result import ValidationResult
from worktop.core_services.app.utility.custom_logger.logging import logger



class ResultBuilderService:
    def build(
        self,
        request: GenerationRequest,
        patches: PatchSet,
        patch_result: PatchWriteResult,
        validation: ValidationResult | None,
        decision_trace: list[DecisionTrace] | None = None,
        repo_profile: RepoProfile | None = None,
        review_reasons: list[str] | None = None,
        *,
        coverage: CoveragePreservationReport | None = None,
        test_value: TestValueReport | None = None,
        traceability: TraceabilityMatrix | None = None,
        review_report: ReviewReport | None = None,
        manifest: GenerationManifest | None = None,
        budget: BudgetReport | None = None,
    ) -> GenerationResult:
        logger.info(
            "[playwright-generation] job_id=%s stage=result_builder status=started",
            request.job_id,
        )
        try:
            diff = "\n".join(applied.diff for applied in patch_result.applied if applied.diff)
            logger.info(
                "[playwright-generation] job_id=%s stage=result_builder status=completed files_changed=%s",
                request.job_id,
                len(patch_result.applied),
            )
            reasons = review_reasons or []
            return GenerationResult(
                job_id=request.job_id,
                files_changed=[applied.path for applied in patch_result.applied],
                diff_summary=f"{len(patch_result.applied)} patch(es) applied",
                diff=diff,
                confidence=0.0,
                needs_review=bool(reasons),
                review_reasons=reasons,
                repo_profile=repo_profile,
                decision_trace=decision_trace or [],
                validation=validation,
                coverage=coverage,
                test_value=test_value,
                traceability=traceability,
                review_report=review_report,
                manifest=manifest,
                budget=budget,
            )
        except Exception as exc:
            logger.exception(
                "[playwright-generation] job_id=%s stage=result_builder status=failed error=%s",
                request.job_id,
                exc,
            )
            raise
