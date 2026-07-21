"""Structured execution plan — plans are data, not just markdown."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import AgentMode, PlanStepStatus


class PlanStep(BaseModel):
    step_id: str
    title: str
    objective: str = ""
    status: PlanStepStatus = PlanStepStatus.PENDING
    depends_on: list[str] = Field(default_factory=list)
    suggested_tools: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    result_summary: str | None = None


class ExecutionPlan(BaseModel):
    plan_id: str
    goal: str
    mode: AgentMode
    steps: list[PlanStep] = Field(default_factory=list)
    current_step_id: str | None = None
    revision: int = 1

    def step(self, step_id: str) -> PlanStep | None:
        return next((s for s in self.steps if s.step_id == step_id), None)

    def first_incomplete(self) -> PlanStep | None:
        return next(
            (s for s in self.steps if s.status in {PlanStepStatus.PENDING, PlanStepStatus.IN_PROGRESS}),
            None,
        )
