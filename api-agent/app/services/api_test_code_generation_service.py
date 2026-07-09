from __future__ import annotations

from app.agents.test_generation_agent import TestGenerationAgent
from app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from app.schemas.api_test_generation_result import ApiTestGenerationResult
from app.schemas.mock_stub_plan import MockStubPlan
from app.schemas.repo_profile import RepoProfile
from app.schemas.source_context import GenerationSourceContext
from app.services.api_test_file_writer import ApiTestFileWriter
from app.validation.api_test_validator import ApiTestValidator


class ApiTestCodeGenerationService:
    def __init__(
        self,
        agent: TestGenerationAgent,
        file_writer: ApiTestFileWriter | None = None,
        validator: ApiTestValidator | None = None,
    ) -> None:
        self.agent = agent
        self.file_writer = file_writer or ApiTestFileWriter()
        self.validator = validator or ApiTestValidator()

    def generate(
        self,
        task_id: str,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
        source_context: GenerationSourceContext | None = None,
        mock_stub_plan: MockStubPlan | None = None,
    ) -> ApiTestGenerationResult:
        output = self.agent.generate(
            request,
            profile,
            source_context=source_context,
            mock_stub_plan=mock_stub_plan,
        )
        generated_files = self.file_writer.write(request.repo_path, output)
        validation = (
            self.validator.validate(
                request.repo_path,
                generated_files,
                profile=profile,
                target=str(request.execution_target),
            )
            if request.run_validation
            else None
        )
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
            warnings=output.warnings,
        )
