from dataclasses import dataclass, field


@dataclass
class PlannedToolCall:
    tool_name: str
    arguments: dict


@dataclass
class ExecutionPlanStep:
    order: int
    description: str
    affected_files: list[str] = field(default_factory=list)
    tool_calls: list[PlannedToolCall] = field(default_factory=list)
    confidence: float | None = None


@dataclass
class ExecutionPlan:
    execution_id: str
    steps: list[ExecutionPlanStep] = field(default_factory=list)
    overall_confidence: float | None = None
