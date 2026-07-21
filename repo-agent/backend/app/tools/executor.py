"""Executes a tool call under mode permission, timeout, and output limits.

The executor is the trust boundary: the LLM proposes a tool; the executor
decides whether it is allowed, runs it safely, and bounds the result.
"""

from __future__ import annotations

import time
from pathlib import Path

from app.config import settings
from app.models.enums import AgentMode
from app.models.tool import ToolCall, ToolResult
from app.tools.base import ToolContext
from app.tools.implementations import TOOL_IMPLEMENTATIONS
from app.tools.registry import (
    ToolPermissionError,
    allowed_tools_for,
    get_tool_definition,
)

try:  # asyncio.timeout exists on 3.11+
    from asyncio import timeout as _timeout
except ImportError:  # pragma: no cover
    _timeout = None


class ToolExecutor:
    async def execute(self, *, workspace: Path, mode: AgentMode, tool_call: ToolCall) -> ToolResult:
        name = tool_call.tool_name
        started = time.perf_counter()

        if name not in allowed_tools_for(mode):
            raise ToolPermissionError(f"{name} is not available in {mode.value} mode")

        impl = TOOL_IMPLEMENTATIONS.get(name)
        definition = get_tool_definition(name)
        if impl is None or definition is None:
            return self._result(tool_call, started, False, f"Unknown tool: {name}")

        ctx = ToolContext(workspace=workspace)
        try:
            if _timeout is not None:
                async with _timeout(definition.timeout_seconds):
                    outcome = await impl(ctx, tool_call.arguments)
            else:  # pragma: no cover
                outcome = await impl(ctx, tool_call.arguments)
        except PermissionError as exc:
            return self._result(tool_call, started, False, f"Blocked: {exc}")
        except TimeoutError:
            return self._result(tool_call, started, False,
                                f"{name} timed out after {definition.timeout_seconds}s",
                                metadata={"timed_out": True})
        except Exception as exc:  # noqa: BLE001 - surfaced as a failed result, never crashes the loop
            return self._result(tool_call, started, False, f"{name} error: {exc}")

        content = outcome.content
        truncated = False
        if content and len(content) > settings.max_tool_output_chars:
            content = content[: settings.max_tool_output_chars]
            truncated = True

        return self._result(
            tool_call, started, outcome.success, outcome.summary,
            content=content, truncated=truncated, metadata=outcome.metadata,
        )

    @staticmethod
    def _result(tool_call: ToolCall, started: float, success: bool, summary: str,
                content: str | None = None, truncated: bool = False,
                metadata: dict | None = None) -> ToolResult:
        return ToolResult(
            tool_call_id=tool_call.tool_call_id, tool_name=tool_call.tool_name,
            success=success, summary=summary, content=content, truncated=truncated,
            metadata=metadata or {}, duration_ms=int((time.perf_counter() - started) * 1000),
        )
