from collections.abc import Iterator

from app.llm.infrastructure.model_client_streaming_adapter import ModelClientStreamingAdapter


class LLMStreamService:
    """Seam for streamed completions. Not wired into chat_service.py/agent_service.py yet —
    both currently use LLMApplicationService's single-shot complete(). Switch a caller to this
    once ModelClientStreamingAdapter is backed by a real streaming method (see that file's
    docstring) and once execution_event_service.py has a token-level SSE event type to carry
    the chunks."""

    def __init__(self, streaming_adapter: ModelClientStreamingAdapter):
        self._streaming_adapter = streaming_adapter

    def stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        return self._streaming_adapter.stream_completion(system_prompt, user_prompt)
