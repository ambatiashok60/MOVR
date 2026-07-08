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

from app.schemas.code_patch import PatchSet, PatchWriteResult
from app.schemas.decision_trace import DecisionTrace
from app.schemas.generation_request import GenerationRequest
from app.schemas.generation_result import GenerationResult
from app.schemas.repo_profile import RepoProfile
from app.schemas.validation_result import ValidationResult


class ResultBuilderService:
    @log_performance("result_builder_service.build")
    def build(
        self,
        request: GenerationRequest,
        patches: PatchSet,
        patch_result: PatchWriteResult,
        validation: ValidationResult | None,
        decision_trace: list[DecisionTrace] | None = None,
        repo_profile: RepoProfile | None = None,
    ) -> GenerationResult:
        log_step("result_builder_started", {"job_id": request.job_id})
        try:
            diff = "\n".join(applied.diff for applied in patch_result.applied if applied.diff)
            logger.info("Generation job completed successfully")
            return GenerationResult(
                job_id=request.job_id,
                files_changed=[applied.path for applied in patch_result.applied],
                diff_summary=f"{len(patch_result.applied)} patch(es) applied",
                diff=diff,
                confidence=0.0,
                repo_profile=repo_profile,
                decision_trace=decision_trace or [],
                validation=validation,
            )
        except Exception as exc:
            log_exception(exc, context={"job_id": request.job_id, "stage": "result_builder"})
            raise
