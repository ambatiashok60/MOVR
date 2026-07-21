import asyncio
from threading import Event

import pytest
from fastapi import HTTPException

from app.resilience import wait_for_agent


class RequestState:
    def __init__(self, disconnected: bool = False):
        self.disconnected = disconnected

    async def is_disconnected(self) -> bool:
        return self.disconnected


def test_agent_wait_returns_completed_result():
    async def scenario():
        task = asyncio.create_task(asyncio.sleep(0, result="done"))
        result = await wait_for_agent(task, Event(), RequestState(), 1)
        assert result == "done"

    asyncio.run(scenario())


def test_agent_wait_times_out_and_signals_worker():
    async def scenario():
        cancel = Event()

        async def worker():
            while not cancel.is_set():
                await asyncio.sleep(0.01)
            return "cancelled"

        task = asyncio.create_task(worker())
        with pytest.raises(HTTPException) as error:
            await wait_for_agent(task, cancel, RequestState(), 0)
        assert error.value.status_code == 504
        assert cancel.is_set()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())


def test_agent_wait_disconnects_without_waiting_for_worker():
    async def scenario():
        cancel = Event()

        async def worker():
            while not cancel.is_set():
                await asyncio.sleep(0.01)
            return "cancelled"

        task = asyncio.create_task(worker())
        result = await wait_for_agent(task, cancel, RequestState(disconnected=True), 5)
        assert result is None
        assert cancel.is_set()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())
