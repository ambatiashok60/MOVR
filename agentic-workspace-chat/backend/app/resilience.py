"""Bounded waiting and safe cleanup for long-running agent tasks."""

import asyncio
from threading import Event

from fastapi import HTTPException, Request

_detached_tasks: set[asyncio.Task] = set()


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
    deadline = loop.time() + timeout_seconds
    while not task.done():
        if await request.is_disconnected():
            cancel_event.set()
            detach_task(task)
            return None
        remaining = deadline - loop.time()
        if remaining <= 0:
            cancel_event.set()
            detach_task(task)
            raise HTTPException(504, f"Agent exceeded the {timeout_seconds}s request deadline")
        await asyncio.sleep(min(0.1, remaining))
    return await task
