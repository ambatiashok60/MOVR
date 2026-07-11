from __future__ import annotations

from worktop.api_agent.app.agents.test_generation_agent import TestGenerationAgent
from worktop.api_agent.app.config import settings
from worktop.api_agent.app.utils.logging_utils import log_step
from worktop.api_agent.app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from worktop.api_agent.app.schemas.api_test_generation_result import ApiTestGenerationResult
from worktop.api_agent.app.schemas.mock_stub_plan import MockStubPlan
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.source_context import GenerationSourceContext
from worktop.api_agent.app.coverage.api_coverage_service import ApiCoverageService
from worktop.api_agent.app.services.api_test_file_writer import ApiTestFileWriter
from worktop.api_agent.app.strategies.strategy_registry import StrategyRegistry
from worktop.api_agent.app.validation.api_test_validator import ApiTestValidator
from worktop.api_agent.app.validation.generated_file_guard import GeneratedFileGuard


class ApiTestCodeGenerationService:
    def __init__(
        self,
        agent: TestGenerationAgent,
        file_writer: ApiTestFileWriter | None = None,
        validator: ApiTestValidator | None = None,
        file_guard: GeneratedFileGuard | None = None,
        strategy_registry: StrategyRegistry | None = None,
    ) -> None:
        self.agent = agent
        self.file_writer = file_writer or ApiTestFileWriter()
        self.validator = validator or ApiTestValidator()
        self.file_guard = file_guard or GeneratedFileGuard()
        self.strategy_registry = strategy_registry or StrategyRegistry()
        self.coverage = ApiCoverageService()

    def generate(
        self,
        task_id: str,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
        source_context: GenerationSourceContext | None = None,
        mock_stub_plan: MockStubPlan | None = None,
        repo_understanding=None,
    ) -> ApiTestGenerationResult:
        output, guard_warnings, review_reasons = self._generate_with_healing(
            request,
            profile,
            source_context,
            mock_stub_plan,
            repo_understanding,
        )
        if not output.files:
            output = self._fallback_output(request, profile, output)
        if any("SCAFFOLD" in warning for warning in output.warnings) or (
            "scaffold" in output.summary.lower()
        ):
            review_reasons.append(
                "Generated files are deterministic scaffold skeletons, not real "
                "coverage; they must be reviewed and completed before merging."
            )

        target_paths = [file.relative_path for file in output.files]
        coverage_before = self.coverage.snapshot_files(request.repo_path, target_paths)
        generated_files = self.file_writer.write(request.repo_path, output)
        validation = (
            self.validator.validate(
                request.repo_path,
                generated_files,
                profile=profile,
                target=str(request.execution_target),
                execute=settings.enable_test_execution,
            )
            if request.run_validation
            else None
        )

        if (
            settings.enable_test_execution
            and validation is not None
            and not validation.passed
        ):
            output, generated_files, validation, execution_warnings = (
                self._execution_repair_round(
                    request, profile, source_context, mock_stub_plan,
                    repo_understanding, output, generated_files, validation,
                )
            )
            guard_warnings = [*guard_warnings, *execution_warnings]
            if validation is not None and not validation.passed:
                review_reasons.append(
                    "Generated tests failed execution after repair; the failure "
                    "output is attached to the validation details."
                )
        # Compare after any execution-repair rewrite so the report reflects
        # what actually landed on disk.
        touched_paths = sorted(
            {*target_paths, *(file.relative_path for file in output.files)}
        )
        coverage_report = self.coverage.compare(
            coverage_before,
            self.coverage.snapshot_files(request.repo_path, touched_paths),
        )
        review_reasons.extend(self.coverage.review_reasons(coverage_report))

        warnings = [*output.warnings, *guard_warnings]
        return ApiTestGenerationResult(
            task_id=task_id,
            user_story_hierarchy_id=request.user_story_hierarchy_id,
            api_scenario_id=request.api_scenario_id,
            generated_files=generated_files,
            validation=validation,
            summary=output.summary,
            strategy_name=output.strategy_name,
            strategy_confidence=output.strategy_confidence,
            strategy_reasons=output.strategy_reasons,
            reused_examples=source_context.existing_test_examples if source_context else [],
            source_files_used=source_context.endpoint_sources if source_context else [],
            mock_stub_plan=mock_stub_plan,
            warnings=warnings,
            needs_review=bool(review_reasons),
            review_reasons=review_reasons,
            coverage=coverage_report,
        )

    def _generate_with_healing(
        self,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
        source_context,
        mock_stub_plan,
        repo_understanding,
    ):
        """Autonomous guard-repair loop (Copilot/Claude Code style self-healing).

        When the write guard rejects generated files, the findings are fed back
        to the model and it regenerates — bounded by
        max_generation_repair_attempts — instead of dropping straight to
        scaffold skeletons. Skeletons remain only the very last resort.
        """
        warnings: list[str] = []
        attempts = max(settings.max_generation_repair_attempts, 0)
        current_request = request
        output = None
        guard_reasons: list[str] = []
        for attempt in range(attempts + 1):
            output = self.agent.generate(
                current_request,
                profile,
                source_context=source_context,
                mock_stub_plan=mock_stub_plan,
                repo_understanding=repo_understanding,
            )
            output, guard_warnings, guard_reasons = self.file_guard.review(
                request.repo_path, output, profile, request,
                mock_stub_plan=mock_stub_plan,
            )
            warnings.extend(guard_warnings)
            mock_gap = any("Mock emission gap" in reason for reason in guard_reasons)
            if mock_gap and attempt < attempts:
                # Missing stubs make CI tests hit real services — important enough
                # to force a healing round rather than ship flagged.
                log_step(
                    "guard_repair_triggered",
                    {"attempt": attempt + 1, "cause": "mock_emission_gap"},
                )
            elif output.files:
                if attempt > 0:
                    warnings.append(
                        f"Self-healing succeeded on attempt {attempt + 1}: the model "
                        "fixed the write-guard findings and produced safe files."
                    )
                return output, warnings, guard_reasons
            if attempt < attempts:
                findings = "\n".join(guard_reasons) or "All files were rejected."
                current_request = request.model_copy(
                    update={
                        "additional_context": (
                            f"{request.additional_context or ''}\n\n"
                            "PREVIOUS ATTEMPT WAS REJECTED BY THE WRITE GUARD. Fix "
                            "every finding below and regenerate ALL files:\n"
                            f"{findings}"
                        ).strip()
                    }
                )
        return output, warnings, guard_reasons

    def _execution_repair_round(
        self,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
        source_context,
        mock_stub_plan,
        repo_understanding,
        output,
        generated_files,
        validation,
    ):
        """Bounded run-fix-rerun loop: feed the real execution failure back to the
        model, re-guard, rewrite, and re-run. This is what turns generated code
        into a proven test instead of a plausible one."""
        warnings: list[str] = []
        for attempt in range(1, max(settings.max_execution_repair_attempts, 0) + 1):
            failure_output = "\n".join(validation.details[-3:])[-6000:]
            repair_request = request.model_copy(
                update={
                    "additional_context": (
                        f"{request.additional_context or ''}\n\n"
                        "PREVIOUS ATTEMPT FAILED EXECUTION. Fix the tests so the "
                        f"command `{validation.command}` passes. Failure output:\n"
                        f"{failure_output}"
                    ).strip()
                }
            )
            repaired = self.agent.generate(
                repair_request,
                profile,
                source_context=source_context,
                mock_stub_plan=mock_stub_plan,
                repo_understanding=repo_understanding,
            )
            repaired, repair_guard_warnings, _ = self.file_guard.review(
                request.repo_path, repaired, profile, request,
                mock_stub_plan=mock_stub_plan,
            )
            warnings.extend(repair_guard_warnings)
            if not repaired.files:
                warnings.append(
                    f"Execution repair attempt {attempt} produced no safe files; "
                    "keeping the previous generation."
                )
                break
            output = repaired
            generated_files = self.file_writer.write(request.repo_path, output)
            validation = self.validator.validate(
                request.repo_path,
                generated_files,
                profile=profile,
                target=str(request.execution_target),
                execute=True,
            )
            if validation.passed:
                warnings.append(
                    f"Execution repair attempt {attempt} fixed the failing tests."
                )
                break
        return output, generated_files, validation, warnings

    def _fallback_output(
        self,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
        rejected_output,
    ):
        """All generated files were rejected: fall back to the deterministic
        strategy skeletons rather than writing nothing (or something unsafe)."""
        strategy_match = self.strategy_registry.select(profile)
        files = strategy_match.strategy.fallback_files(request, profile)
        return rejected_output.model_copy(
            update={
                "files": files,
                "summary": (
                    "SCAFFOLD: deterministic fallback API test skeletons using "
                    f"{strategy_match.strategy.strategy_name} after the write guard "
                    "rejected the model output. Not real coverage."
                ),
                "strategy_name": strategy_match.strategy.strategy_name,
                "strategy_confidence": strategy_match.confidence,
                "strategy_reasons": strategy_match.reasons,
            }
        )
