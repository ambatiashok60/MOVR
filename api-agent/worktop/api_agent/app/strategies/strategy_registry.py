from __future__ import annotations

from worktop.api_agent.app.schemas.repo_profile import RepoProfile
from worktop.api_agent.app.strategies.base_strategy import ApiTestGenerationStrategy, StrategyMatch
from worktop.api_agent.app.strategies.java_spring_mockmvc_strategy import JavaSpringMockMvcStrategy
from worktop.api_agent.app.strategies.java_spring_rest_assured_strategy import JavaSpringRestAssuredStrategy
from worktop.api_agent.app.strategies.python_fastapi_testclient_strategy import PythonFastApiTestClientStrategy
from worktop.api_agent.app.strategies.python_pytest_httpx_strategy import PythonPytestHttpxStrategy


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: list[ApiTestGenerationStrategy] = [
            JavaSpringMockMvcStrategy(),
            JavaSpringRestAssuredStrategy(),
            PythonFastApiTestClientStrategy(),
            PythonPytestHttpxStrategy(),
        ]

    def register(self, strategy: ApiTestGenerationStrategy) -> None:
        """Add or replace a strategy without modifying orchestration code."""
        self._strategies = [
            item for item in self._strategies
            if item.strategy_name != strategy.strategy_name
        ]
        self._strategies.append(strategy)

    def registered(self) -> list[str]:
        return sorted(strategy.strategy_name for strategy in self._strategies)

    def select(self, profile: RepoProfile) -> StrategyMatch:
        matches = [
            strategy.match(profile)
            for strategy in self._strategies
            if strategy.supports(profile)
        ]
        if matches:
            return sorted(matches, key=self._confidence_rank, reverse=True)[0]
        return self._fallback(profile)

    def _confidence_rank(self, match: StrategyMatch) -> int:
        return {"high": 3, "medium": 2, "low": 1}.get(match.confidence, 0)

    def _fallback(self, profile: RepoProfile) -> StrategyMatch:
        if profile.team_strategy.primary_language == "python":
            strategy = PythonPytestHttpxStrategy()
            return StrategyMatch(
                strategy=strategy,
                confidence="low",
                reasons=["Python was detected, but no precise API test strategy matched."],
                warnings=["Using generic pytest HTTP fallback strategy."],
            )
        strategy = JavaSpringMockMvcStrategy()
        return StrategyMatch(
            strategy=strategy,
            confidence="low",
            reasons=["No precise API test strategy matched."],
            warnings=["Using generic Java/Spring MockMvc fallback strategy."],
        )
