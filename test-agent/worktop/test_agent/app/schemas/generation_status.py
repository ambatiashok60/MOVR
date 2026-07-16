"""Single source of truth for generation status vocabulary.

Two vocabularies exist deliberately:

* internal job-store lifecycle statuses (lowercase) used for state management;
* external SSE statuses (CamelCase) kept frontend-compatible with the existing
  script-generation stream.

Map centrally through :data:`SSE_STATUS_BY_JOB_STATUS` / :func:`to_sse_status`
so string mappings never get scattered across routes and workers.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Internal job-store lifecycle statuses
# --------------------------------------------------------------------------- #
JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_ABORT_REQUESTED = "abort_requested"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"
JOB_ABORTED = "aborted"

TERMINAL_JOB_STATUSES: frozenset[str] = frozenset(
    {JOB_COMPLETED, JOB_FAILED, JOB_ABORTED}
)

# --------------------------------------------------------------------------- #
# External SSE-facing statuses (must stay compatible with the existing UI)
# --------------------------------------------------------------------------- #
SSE_IN_PROGRESS = "InProgress"
SSE_COMPLETED = "Completed"
SSE_FAILED = "Failed"
SSE_ABORTING = "Aborting"
SSE_ABORTED = "Aborted"

TERMINAL_SSE_STATUSES: frozenset[str] = frozenset(
    {SSE_COMPLETED, SSE_FAILED, SSE_ABORTED}
)

SSE_STATUS_BY_JOB_STATUS: dict[str, str] = {
    JOB_QUEUED: SSE_IN_PROGRESS,
    JOB_RUNNING: SSE_IN_PROGRESS,
    JOB_ABORT_REQUESTED: SSE_ABORTING,
    JOB_COMPLETED: SSE_COMPLETED,
    JOB_FAILED: SSE_FAILED,
    JOB_ABORTED: SSE_ABORTED,
}


def to_sse_status(job_status: str) -> str:
    """Translate an internal job status to its frontend-facing SSE status."""
    return SSE_STATUS_BY_JOB_STATUS.get(job_status, SSE_IN_PROGRESS)
