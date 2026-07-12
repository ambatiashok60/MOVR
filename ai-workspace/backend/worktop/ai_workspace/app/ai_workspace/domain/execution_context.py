from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .workspace_mode import WorkspaceMode


class ExecutionStatus(str, Enum):
    PLANNING = "planning"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionStageStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    FAILED = "failed"


@dataclass
class ExecutionStage:
    """Coarse-grained timeline entry (one row in the frontend's execution timeline), distinct
    from execution_event.py's ExecutionEvent (one SSE frame). A stage typically corresponds to
    many events — this is the aggregate a stage settles into once its events stop arriving."""

    id: str
    label: str
    status: ExecutionStageStatus
    detail: str | None = None


@dataclass
class ExecutionContext:
    """One Ask/Agent run. Threaded through ExecutionOrchestrator and every strategy/service
    it calls, so nothing downstream needs to re-derive session/mode/tenant. Mutated in place
    as the run progresses (status, stages) — the orchestrator returns this same object at the
    end, which the API layer then maps into ExecutionRunDto alongside a separate lookup of
    this run's FileChange list from review_service.py (execution_id doubles as run_id)."""

    execution_id: str
    session_id: str
    tenant_id: str
    mode: WorkspaceMode
    prompt: str
    correlation_id: str
    started_at: datetime
    status: ExecutionStatus = ExecutionStatus.PLANNING
    stages: list[ExecutionStage] = field(default_factory=list)
    completed_at: datetime | None = None
    error_message: str | None = None
    needs_review: bool = False
    review_reasons: list[str] = field(default_factory=list)
    budget_usage: dict[str, int | float] = field(default_factory=dict)
    engineering_review: dict = field(default_factory=dict)
    isolated_workspace_path: str | None = None
