"""Execution tools (Agent mode only).

Structured `create_subprocess_exec` only — never a shell string. Allowlisted
executables, timeout, output truncation, process-tree termination on timeout.
"""

from __future__ import annotations

import asyncio

from app.config import settings
from app.tools.base import ToolContext, ToolOutcome
from app.tools.implementations import read_tools

ALLOWED_EXECUTABLES = frozenset({
    "python", "python3", "pytest", "ruff", "mypy", "black",
    "npm", "npx", "ng", "node", "yarn", "pnpm",
    "mvn", "mvnw", "gradle", "gradlew", "git", "go", "cargo",
})


async def run_command(ctx: ToolContext, args: dict) -> ToolOutcome:
    executable = str(args.get("executable", "")).strip()
    if executable not in ALLOWED_EXECUTABLES:
        return ToolOutcome(False, f"Executable not allowed: {executable!r}",
                           None, {"allowed": sorted(ALLOWED_EXECUTABLES)})
    arguments = [str(a) for a in args.get("arguments", [])]
    cwd = ctx.path_guard.resolve_inside_workspace(ctx.workspace, args.get("cwd_relative", "."))
    timeout = int(args.get("timeout_seconds", settings.default_command_timeout_seconds))

    try:
        proc = await asyncio.create_subprocess_exec(
            executable, *arguments, cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return ToolOutcome(False, f"Command not found on PATH: {executable}")

    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return ToolOutcome(False, f"Command timed out after {timeout}s: {executable}",
                           None, {"timed_out": True})

    combined = ((out or b"") + (err or b"")).decode(errors="replace")
    combined = combined[: settings.max_command_output_chars]
    ok = proc.returncode == 0
    return ToolOutcome(
        ok, f"{executable} exited {proc.returncode}", combined,
        {"exit_code": proc.returncode, "command": [executable, *arguments]},
    )


async def _detected(ctx: ToolContext, key: str) -> list[str] | None:
    outcome = await read_tools.detect_project_commands(ctx, {})
    return outcome.metadata.get("commands", {}).get(key)


async def _run_detected(ctx: ToolContext, key: str, label: str) -> ToolOutcome:
    command = await _detected(ctx, key)
    if not command:
        return ToolOutcome(True, f"No {label} command detected; skipped",
                           None, {"skipped": True})
    return await run_command(ctx, {"executable": command[0], "arguments": command[1:]})


async def run_tests(ctx: ToolContext, args: dict) -> ToolOutcome:
    return await _run_detected(ctx, "test", "test")


async def run_linter(ctx: ToolContext, args: dict) -> ToolOutcome:
    return await _run_detected(ctx, "lint", "lint")


async def run_type_check(ctx: ToolContext, args: dict) -> ToolOutcome:
    return await _run_detected(ctx, "type_check", "type-check")


async def run_build(ctx: ToolContext, args: dict) -> ToolOutcome:
    return await _run_detected(ctx, "build", "build")
