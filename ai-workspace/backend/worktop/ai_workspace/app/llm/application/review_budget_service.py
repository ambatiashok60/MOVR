from __future__ import annotations
from dataclasses import dataclass, field
from time import perf_counter

@dataclass
class BudgetUsage:
    llm_calls: int = 0
    prompt_characters: int = 0
    completion_characters: int = 0
    elapsed_seconds: float = 0.0

@dataclass
class BudgetReview:
    usage: BudgetUsage
    review_required: bool = False
    findings: list[str] = field(default_factory=list)

class ReviewBudgetService:
    """Review-only estimates. It deliberately never raises or blocks execution."""
    def __init__(self, max_llm_calls: int, max_prompt_characters: int, max_seconds: float) -> None:
        self.max_llm_calls = max_llm_calls
        self.max_prompt_characters = max_prompt_characters
        self.max_seconds = max_seconds
        self._usage: dict[str, BudgetUsage] = {}
        self._started: dict[str, float] = {}

    def charge(self, execution_id: str, prompt_chars: int, completion_chars: int) -> None:
        usage = self._usage.setdefault(execution_id, BudgetUsage())
        self._started.setdefault(execution_id, perf_counter())
        usage.llm_calls += 1
        usage.prompt_characters += max(prompt_chars, 0)
        usage.completion_characters += max(completion_chars, 0)

    def report(self, execution_id: str) -> BudgetReview:
        usage = self._usage.setdefault(execution_id, BudgetUsage())
        started = self._started.get(execution_id, perf_counter())
        usage.elapsed_seconds = round(perf_counter() - started, 3)
        findings: list[str] = []
        if usage.llm_calls > self.max_llm_calls:
            findings.append(f"LLM calls estimated at {usage.llm_calls}; review threshold is {self.max_llm_calls}.")
        if usage.prompt_characters > self.max_prompt_characters:
            findings.append(f"Prompt characters estimated at {usage.prompt_characters}; review threshold is {self.max_prompt_characters}.")
        if usage.elapsed_seconds > self.max_seconds:
            findings.append(f"Execution took {usage.elapsed_seconds}s; review threshold is {self.max_seconds}s.")
        return BudgetReview(usage=usage, review_required=bool(findings), findings=findings)
