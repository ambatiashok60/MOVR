from __future__ import annotations

import logging
from time import perf_counter

from worktop.test_agent.app.config import settings
from worktop.test_agent.app.schemas.generation_budget import BudgetLimits, BudgetReport, BudgetUsage
from worktop.core_services.app.utility.custom_logger.logging import logger



class BudgetExceededError(RuntimeError):
    """A generation run hit a hard cost/latency ceiling and must escalate.

    Escalation means the run stops with an explicit, human-actionable reason
    instead of burning more model calls, tool calls, or wall-clock time.
    """

    def __init__(self, reason: str, report: BudgetReport) -> None:
        super().__init__(reason)
        self.report = report


class GenerationBudget:
    """Track and cap the cost of one generation run.

    Every LLM call, tool call, repository read, and repair attempt is charged
    against limits; exceeding any limit raises BudgetExceededError so agents
    can never loop forever or silently rack up spend.
    """

    def __init__(
        self,
        limits: BudgetLimits | None = None,
        enforcement_mode: str | None = None,
    ) -> None:
        self.limits = limits or BudgetLimits(
            max_llm_calls=settings.budget_max_llm_calls,
            max_tool_calls=settings.budget_max_tool_calls,
            max_repository_reads=settings.budget_max_repository_reads,
            max_prompt_chars=settings.budget_max_prompt_chars,
            max_generation_seconds=settings.budget_max_generation_seconds,
        )
        self.usage = BudgetUsage()
        self._started_at = perf_counter()
        self._escalation_reason = ""
        self.enforcement_mode = (enforcement_mode or settings.budget_enforcement_mode).lower()
        self._exceeded_thresholds: list[str] = []

    def charge_llm_call(self, prompt_chars: int = 0, completion_chars: int = 0) -> None:
        self.usage.llm_calls += 1
        self.usage.prompt_chars += max(prompt_chars, 0)
        self.usage.completion_chars += max(completion_chars, 0)
        self._enforce("llm_calls", self.usage.llm_calls, self.limits.max_llm_calls)
        self._enforce(
            "prompt_chars", self.usage.prompt_chars, self.limits.max_prompt_chars
        )

    def charge_tool_call(self) -> None:
        self.usage.tool_calls += 1
        self._enforce("tool_calls", self.usage.tool_calls, self.limits.max_tool_calls)

    def charge_repository_read(self) -> None:
        self.usage.repository_reads += 1
        self._enforce(
            "repository_reads",
            self.usage.repository_reads,
            self.limits.max_repository_reads,
        )

    def charge_repair_attempt(self) -> None:
        self.usage.repair_attempts += 1
        self._check_time()

    def report(self) -> BudgetReport:
        self.usage.elapsed_seconds = round(perf_counter() - self._started_at, 3)
        return BudgetReport(
            limits=self.limits,
            usage=self.usage.model_copy(),
            escalated=bool(self._escalation_reason),
            escalation_reason=self._escalation_reason,
            enforcement_mode=self.enforcement_mode,
            review_required=bool(self._exceeded_thresholds),
            exceeded_thresholds=list(self._exceeded_thresholds),
        )

    def _enforce(self, name: str, used: int, limit: int) -> None:
        self._check_time()
        if used <= limit:
            return
        self._escalate(
            f"Generation budget exceeded: {name} used {used} of {limit} allowed."
        )

    def _check_time(self) -> None:
        elapsed = perf_counter() - self._started_at
        self.usage.elapsed_seconds = round(elapsed, 3)
        if elapsed > self.limits.max_generation_seconds:
            self._escalate(
                "Generation budget exceeded: "
                f"elapsed {elapsed:.0f}s of {self.limits.max_generation_seconds:.0f}s allowed."
            )

    def _escalate(self, reason: str) -> None:
        self._escalation_reason = reason
        if reason not in self._exceeded_thresholds:
            self._exceeded_thresholds.append(reason)
        report = self.report()
        logger.log(logging.ERROR if self.enforcement_mode == 'strict' else logging.WARNING, "[playwright-generation] stage=%s | status=%s | details=%s", 'generation_budget', 'blocked' if self.enforcement_mode == 'strict' else 'review_required', {'reason': reason, 'enforcement_mode': self.enforcement_mode, 'usage': report.usage.model_dump()})
        if self.enforcement_mode == "strict":
            raise BudgetExceededError(reason, report)


class BudgetedLLMClient:
    """LLMClient wrapper that charges every model call against the budget."""

    def __init__(self, inner: object, budget: GenerationBudget) -> None:
        self._inner = inner
        self._budget = budget

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        self._budget.charge_llm_call(prompt_chars=len(prompt))
        # Forward system_prompt only when supplied so inner clients that predate
        # the parameter (older adapters, test doubles) keep working.
        extra = {"system_prompt": system_prompt} if system_prompt is not None else {}
        result = self._inner.complete(prompt, **extra)  # type: ignore[attr-defined]
        self._budget.usage.completion_chars += len(result or "")
        return result

    def complete_structured(
        self,
        prompt: str,
        response_model: type,
        system_prompt: str | None = None,
    ) -> object:
        self._budget.charge_llm_call(prompt_chars=len(prompt))
        extra = {"system_prompt": system_prompt} if system_prompt is not None else {}
        return self._inner.complete_structured(  # type: ignore[attr-defined]
            prompt=prompt,
            response_model=response_model,
            **extra,
        )

    def charge_tool_call(self) -> None:
        self._budget.charge_tool_call()

    def charge_repository_read(self) -> None:
        self._budget.charge_repository_read()
