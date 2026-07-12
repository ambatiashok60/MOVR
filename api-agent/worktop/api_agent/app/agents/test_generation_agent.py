from __future__ import annotations

from worktop.api_agent.app.agents.base_agent import BaseAgent
from worktop.api_agent.app.prompts.api_test_code_prompt import build_api_test_code_prompt
from worktop.api_agent.app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from worktop.api_agent.app.schemas.llm_outputs import TestCodeOutput, TestCodeTurn
from worktop.api_agent.app.schemas.mock_stub_plan import MockStubPlan
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.source_context import GenerationSourceContext
from worktop.api_agent.app.strategies.strategy_registry import StrategyRegistry


class TestGenerationAgent(BaseAgent):
    agent_name = "api_test_generation_agent"

    def __init__(self, *args, strategy_registry: StrategyRegistry | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.strategy_registry = strategy_registry or StrategyRegistry()

    def generate(
        self,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
        source_context: GenerationSourceContext | None = None,
        mock_stub_plan: MockStubPlan | None = None,
        repo_understanding=None,
    ) -> TestCodeOutput:
        self.log_start(
            "generating_test_code",
            scenario_id=request.api_scenario_id,
            target=str(request.execution_target),
        )
        strategy_match = self.strategy_registry.select(profile)
        strategy_guidance = strategy_match.strategy.prompt_guidance(profile)
        prompt = build_api_test_code_prompt(
            request,
            profile,
            strategy_guidance=strategy_guidance,
            source_context=source_context,
            mock_stub_plan=mock_stub_plan,
            repo_understanding=repo_understanding,
            include_contract=False,
        )
        prompt += (
            "\n\nBefore concluding, read any source you are about to reference "
            "(DTOs, controllers, helpers, fixtures) so every field name, import, "
            "and helper call in the generated tests is real, not guessed."
        )
        try:
            output = self.complete_with_exploration(
                prompt, TestCodeTurn, request.repo_path
            )
        except Exception:
            output = self._fallback_code(request, profile, strategy_match)
        if output.files:
            output.strategy_name = output.strategy_name or strategy_match.strategy.strategy_name
            output.strategy_confidence = output.strategy_confidence or strategy_match.confidence
            output.strategy_reasons = output.strategy_reasons or strategy_match.reasons
            output.warnings = [
                *strategy_match.warnings,
                *output.warnings,
            ]
            return output
        return self._fallback_code(request, profile, strategy_match)

    def _fallback_code(
        self,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
        strategy_match,
    ) -> TestCodeOutput:
        files = strategy_match.strategy.fallback_files(request, profile)
        return TestCodeOutput(
            files=files,
            summary=f"Generated fallback API test skeletons using {strategy_match.strategy.strategy_name}.",
            strategy_name=strategy_match.strategy.strategy_name,
            strategy_confidence=strategy_match.confidence,
            strategy_reasons=strategy_match.reasons,
            warnings=[
                *strategy_match.warnings,
                "SCAFFOLD: deterministic strategy skeleton files were used because "
                "model output was unavailable. These are placeholders, not real "
                "coverage; manual review required.",
            ],
        )
