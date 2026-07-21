"""Streams a semantic response section as SSE deltas while guarding Markdown
code-fence integrity (§16).

A batch never finalizes with an open code fence: if the model stops mid-fence,
the batcher appends a closing fence before emitting `response_batch_completed`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.llm.base import LLMClient
from app.models.enums import ResponseBatchType, StreamEventType
from app.models.response import ResponseBatch, ResponseSection
from app.persistence.repositories import RunArtifactRepository
from app.streaming.event_bus import EventBus


@dataclass
class MarkdownStreamState:
    inside_code_fence: bool = False
    fence_marker: str | None = None

    def observe(self, text: str) -> None:
        for line in text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("```"):
                if not self.inside_code_fence:
                    self.inside_code_fence = True
                    self.fence_marker = "```"
                else:
                    self.inside_code_fence = False
                    self.fence_marker = None

    def closing_if_needed(self) -> str:
        return "\n```\n" if self.inside_code_fence else ""


class ResponseBatcher:
    def __init__(self, bus: EventBus, artifacts: RunArtifactRepository) -> None:
        self._bus = bus
        self._artifacts = artifacts

    async def stream_section(
        self, *, run_id: str, index: int, section: ResponseSection,
        llm: LLMClient, shared_context: dict,
    ) -> ResponseBatch:
        batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        batch = ResponseBatch(batch_id=batch_id, run_id=run_id, index=index,
                              type=section.type, title=section.title)

        await self._bus.publish(run_id, StreamEventType.RESPONSE_BATCH_STARTED, {
            "batch_id": batch_id, "index": index, "type": section.type.value, "title": section.title,
        })

        state = MarkdownStreamState()
        sequence = 0
        async for delta in llm.stream_section(section=section, shared_context=shared_context):
            if not delta:
                continue
            sequence += 1
            state.observe(delta)
            batch.markdown += delta
            await self._bus.publish(run_id, StreamEventType.RESPONSE_DELTA, {
                "batch_id": batch_id, "delta_index": sequence, "delta": delta,
            })

        # Never leave a batch with a dangling code fence.
        closing = state.closing_if_needed()
        if closing:
            batch.markdown += closing
            await self._bus.publish(run_id, StreamEventType.RESPONSE_DELTA, {
                "batch_id": batch_id, "delta_index": sequence + 1, "delta": closing,
            })

        batch.is_final = section.type == ResponseBatchType.SUMMARY
        self._artifacts.save_response_batch(batch)
        await self._bus.publish(run_id, StreamEventType.RESPONSE_BATCH_COMPLETED, {
            "batch_id": batch_id, "index": index,
        })
        return batch
