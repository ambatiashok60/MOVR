from __future__ import annotations

from pydantic import BaseModel, Field


class BudgetLimits(BaseModel):
    """Hard ceilings for one generation run; beyond them the run escalates."""

    max_llm_calls: int = 40
    max_tool_calls: int = 60
    max_repository_reads: int = 200
    max_prompt_chars: int = 1_500_000
    max_generation_seconds: float = 900.0


class BudgetUsage(BaseModel):
    llm_calls: int = 0
    tool_calls: int = 0
    repository_reads: int = 0
    repair_attempts: int = 0
    prompt_chars: int = 0
    completion_chars: int = 0
    elapsed_seconds: float = 0.0


class BudgetReport(BaseModel):
    limits: BudgetLimits = Field(default_factory=BudgetLimits)
    usage: BudgetUsage = Field(default_factory=BudgetUsage)
    escalated: bool = False
    escalation_reason: str = ""
