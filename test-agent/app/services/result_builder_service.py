from __future__ import annotations

import logging


from app.schemas.code_patch import PatchSet, PatchWriteResult
from app.schemas.coverage import CoveragePreservationReport
from app.schemas.decision_trace import DecisionTrace
from app.schemas.generation_request import GenerationRequest
from app.schemas.generation_result import GenerationResult
from app.schemas.repo_profile import RepoProfile
from app.schemas.test_value import TestValueReport
from app.schemas.validation_result import ValidationResult

logger = logging.getLogger(__name__)


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
            )
        except Exception as exc:
            logger.exception(
                "[playwright-generation] job_id=%s stage=result_builder status=failed error=%s",
                request.job_id,
                exc,
            )
            raise
