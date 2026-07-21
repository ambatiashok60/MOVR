"""Correlation identifiers propagated implicitly via contextvars.

Any log emitted while these are set automatically carries the ids, so services
never have to thread run/tool identifiers through every logging call.
"""

from __future__ import annotations

from contextvars import ContextVar

run_id_ctx: ContextVar[str | None] = ContextVar("run_id", default=None)
conversation_id_ctx: ContextVar[str | None] = ContextVar("conversation_id", default=None)
workspace_id_ctx: ContextVar[str | None] = ContextVar("workspace_id", default=None)
plan_id_ctx: ContextVar[str | None] = ContextVar("plan_id", default=None)
plan_step_id_ctx: ContextVar[str | None] = ContextVar("plan_step_id", default=None)
tool_call_id_ctx: ContextVar[str | None] = ContextVar("tool_call_id", default=None)
response_batch_id_ctx: ContextVar[str | None] = ContextVar("response_batch_id", default=None)

_ALL = {
    "run_id": run_id_ctx,
    "conversation_id": conversation_id_ctx,
    "workspace_id": workspace_id_ctx,
    "plan_id": plan_id_ctx,
    "plan_step_id": plan_step_id_ctx,
    "tool_call_id": tool_call_id_ctx,
    "response_batch_id": response_batch_id_ctx,
}


def current_correlation() -> dict[str, str]:
    """Snapshot of all non-empty correlation ids currently in scope."""
    return {name: var.get() for name, var in _ALL.items() if var.get() is not None}
