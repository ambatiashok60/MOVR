"""Enumerations that form the backend<->frontend contract.

The string VALUES here are the single source of truth. The frontend uses the
same lowercase values (see docs/integration-contract.md) so the two never drift.
"""

from __future__ import annotations

from enum import StrEnum


class AgentMode(StrEnum):
    ASK = "ask"
    AGENT = "agent"


class RunStatus(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_FOR_AUTH = "waiting_for_auth"
    VALIDATING = "validating"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}


class AgentState(StrEnum):
    """Internal Plan-Act-Observe-Decide state machine."""

    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    SELECTING_ACTION = "selecting_action"
    EXECUTING_TOOL = "executing_tool"
    OBSERVING = "observing"
    UPDATING_PLAN = "updating_plan"
    VALIDATING = "validating"
    RESPONDING = "responding"
    COMPLETED = "completed"
    FAILED = "failed"


class PlanStepStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class ResponseBatchType(StrEnum):
    PLAN = "plan"
    PROGRESS = "progress"
    REPOSITORY_FINDINGS = "repository_findings"
    EXPLANATION = "explanation"
    CODE_SUGGESTION = "code_suggestion"
    CODE_CHANGE = "code_change"
    DIFF = "diff"
    VALIDATION = "validation"
    WARNING = "warning"
    SUMMARY = "summary"


class StreamEventType(StrEnum):
    RUN_STARTED = "run_started"
    PLAN_CREATED = "plan_created"
    PLAN_UPDATED = "plan_updated"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    OBSERVATION_CREATED = "observation_created"
    RESPONSE_BATCH_STARTED = "response_batch_started"
    RESPONSE_DELTA = "response_delta"
    RESPONSE_BATCH_COMPLETED = "response_batch_completed"
    AWS_REAUTHENTICATION_REQUIRED = "aws_reauthentication_required"
    AWS_REAUTHENTICATED = "aws_reauthenticated"
    VALIDATION_STARTED = "validation_started"
    VALIDATION_COMPLETED = "validation_completed"
    CONVERSATION_COMPACTED = "conversation_compacted"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    HEARTBEAT = "heartbeat"
