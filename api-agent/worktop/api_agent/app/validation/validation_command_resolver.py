from __future__ import annotations

from worktop.api_agent.app.schemas.execution_target import ExecutionTarget
from worktop.api_agent.app.schemas.repo_profile import RepoProfile


class ValidationCommandResolver:
    def resolve(self, profile: RepoProfile, target: ExecutionTarget | str) -> list[str]:
        target_value = str(target)
        if target_value == str(ExecutionTarget.STAGE) and profile.team_strategy.stage_command:
            return [profile.team_strategy.stage_command]
        if target_value == str(ExecutionTarget.CI) and profile.team_strategy.ci_command:
            return [profile.team_strategy.ci_command]
        if profile.team_strategy.ci_command:
            return [profile.team_strategy.ci_command]
        return profile.team_strategy.validation_commands
