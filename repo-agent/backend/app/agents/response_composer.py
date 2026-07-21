"""Streams the final answer as a manifest of semantic sections (§15).

Each section is generated and streamed independently so no single section can
consume the whole budget and code fences stay valid across the stream.
"""

from __future__ import annotations

from app.llm.base import LLMClient
from app.llm.fake_llm import _keywords
from app.models.enums import AgentMode
from app.streaming.event_bus import EventBus
from app.streaming.response_batcher import ResponseBatcher
from app.persistence.repositories import RunArtifactRepository


class ResponseComposer:
    def __init__(self, bus: EventBus, artifacts: RunArtifactRepository, llm: LLMClient) -> None:
        self._bus = bus
        self._batcher = ResponseBatcher(bus, artifacts)
        self._llm = llm

    async def stream_final_response(
        self, *, run_id: str, user_request: str, mode: AgentMode,
        observations: list[str], changed_files: list[str], validation: list[str],
    ) -> int:
        sections = await self._llm.plan_response_sections(
            user_request=user_request, mode=mode, observations=observations
        )
        shared_context = {
            "user_request": user_request,
            "keywords": _keywords(user_request),
            "mode": mode.value,
            "changed_files": changed_files,
            "validation": validation,
            "observation_count": len(observations),
        }
        for index, section in enumerate(sections):
            await self._batcher.stream_section(
                run_id=run_id, index=index, section=section,
                llm=self._llm, shared_context=shared_context,
            )
        return len(sections)
