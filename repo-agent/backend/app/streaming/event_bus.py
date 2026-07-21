"""In-memory pub/sub for run events, backed by persistence for replay.

Each event gets a monotonic per-run sequence number. Publishing persists the
event (so a late/reconnecting subscriber can replay) and fans it out to live
subscribers. A heartbeat keeps idle connections (and the frontend watchdog)
alive.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from functools import lru_cache

from app.config import settings
from app.models.enums import StreamEventType
from app.models.stream import StreamEvent
from app.persistence.database import get_database
from app.persistence.repositories import EventRepository, RunRepository


class EventBus:
    def __init__(self) -> None:
        self._sequences: dict[str, int] = defaultdict(int)
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._terminal: set[str] = set()
        db = get_database()
        self._events = EventRepository(db)
        self._runs = RunRepository(db)

    async def publish(self, run_id: str, event_type: StreamEventType, payload: dict) -> StreamEvent:
        async with self._locks[run_id]:
            self._sequences[run_id] += 1
            sequence = self._sequences[run_id]

        event = StreamEvent(run_id=run_id, sequence=sequence, event_type=event_type, payload=payload)

        # Persist for replay, advance the run's authoritative last-sequence.
        self._events.append(run_id, sequence, event_type.value, payload, event.created_at.isoformat())
        self._runs.touch_activity(run_id, sequence)

        for queue in list(self._subscribers.get(run_id, set())):
            queue.put_nowait(event)

        if event_type in {StreamEventType.RUN_COMPLETED, StreamEventType.RUN_FAILED,
                          StreamEventType.RUN_CANCELLED}:
            self._terminal.add(run_id)
        return event

    def is_terminal(self, run_id: str) -> bool:
        return run_id in self._terminal

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[run_id].add(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        self._subscribers.get(run_id, set()).discard(queue)

    def replay_after(self, run_id: str, after_sequence: int) -> list[dict]:
        # Restore the sequence counter after a process restart so new events
        # continue monotonically.
        persisted = self._events.list_after(run_id, -1)
        if persisted:
            self._sequences[run_id] = max(self._sequences[run_id], persisted[-1]["sequence"])
        return self._events.list_after(run_id, after_sequence)

    def current_sequence(self, run_id: str) -> int:
        return self._sequences[run_id]

    @property
    def heartbeat_interval(self) -> int:
        return settings.heartbeat_interval_seconds


@lru_cache
def get_event_bus() -> EventBus:
    return EventBus()
