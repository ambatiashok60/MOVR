from __future__ import annotations

from worktop.api_agent.app.agents.base_agent import BaseAgent
from worktop.api_agent.app.prompts.strategy_reasoning_prompt import build_strategy_reasoning_prompt
from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.schemas.strategy_reasoning import StrategyReasoningOutput


class StrategyReasoningAgent(BaseAgent):
    agent_name = "strategy_reasoning_agent"

    def review(self, profile: RepoProfile) -> StrategyReasoningOutput:
        self.log_start("reviewing_capability_strategy")
        return self.complete_structured(build_strategy_reasoning_prompt(profile), StrategyReasoningOutput)
