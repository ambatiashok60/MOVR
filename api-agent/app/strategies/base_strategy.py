from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.schemas.api_test_generation_request import GenerateApiTestCodeRequest
from app.schemas.execution_target import ExecutionTarget
from app.schemas.llm_outputs import GeneratedTestFileOutput
from app.schemas.repo_profile import RepoProfile


@dataclass(frozen=True)
class StrategyMatch:
    strategy: "ApiTestGenerationStrategy"
    confidence: str
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ApiTestGenerationStrategy(ABC):
    strategy_name = "base"
    target_language = "unknown"
    test_framework = "unknown"

    @abstractmethod
    def supports(self, profile: RepoProfile) -> bool:
        ...

    @abstractmethod
    def match(self, profile: RepoProfile) -> StrategyMatch:
        ...

    @abstractmethod
    def fallback_files(
        self,
        request: GenerateApiTestCodeRequest,
        profile: RepoProfile,
    ) -> list[GeneratedTestFileOutput]:
        ...

    def validation_commands(
        self,
        profile: RepoProfile,
        target: ExecutionTarget,
    ) -> list[str]:
        if target == ExecutionTarget.STAGE and profile.team_strategy.stage_command:
            return [profile.team_strategy.stage_command]
        if profile.team_strategy.ci_command:
            return [profile.team_strategy.ci_command]
        return profile.team_strategy.validation_commands

    def prompt_guidance(self, profile: RepoProfile) -> str:
        return (
            f"Use strategy {self.strategy_name} with {self.target_language} "
            f"and {self.test_framework}."
        )

    def _targets(self, request: GenerateApiTestCodeRequest) -> list[ExecutionTarget]:
        if request.execution_target == ExecutionTarget.BOTH:
            return [ExecutionTarget.CI, ExecutionTarget.STAGE]
        return [request.execution_target]
