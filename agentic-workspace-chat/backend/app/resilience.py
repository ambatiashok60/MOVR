"""Bounded waiting and safe cleanup for long-running agent tasks."""

import asyncio
import logging
from threading import Event

from fastapi import HTTPException, Request

_detached_tasks: set[asyncio.Task] = set()
logger = logging.getLogger("agentic-workspace-chat.resilience")


def detach_task(task: asyncio.Task) -> None:
    """Keep a disconnected task alive only until its worker exits."""
    _detached_tasks.add(task)

    def finished(done: asyncio.Task) -> None:
        _detached_tasks.discard(done)
        try:
            done.result()
        except BaseException:  # cancellation/provider errors are already reported
            pass

    task.add_done_callback(finished)


async def wait_for_agent(task: asyncio.Task, cancel_event: Event, request: Request, timeout_seconds: int):
    """Wait without dead-hanging on a disconnected client or provider call."""
    loop = asyncio.get_running_loop()
    started = loop.time()
    deadline = loop.time() + timeout_seconds
    next_heartbeat = started + 10
    while not task.done():
        if await request.is_disconnected():
            logger.warning("Client disconnected; agent cancellation requested")
            cancel_event.set()
            detach_task(task)
            return None
        remaining = deadline - loop.time()
        if remaining <= 0:
            logger.error("Agent deadline exceeded timeout_seconds=%s", timeout_seconds)
            cancel_event.set()
            detach_task(task)
            raise HTTPException(504, f"Agent exceeded the {timeout_seconds}s request deadline")
        if loop.time() >= next_heartbeat:
            logger.info(
                "Agent still running elapsed_seconds=%s deadline_remaining_seconds=%s",
                round(loop.time() - started), round(remaining),
            )
            next_heartbeat = loop.time() + 10
        await asyncio.sleep(min(0.1, remaining))
    return await task
