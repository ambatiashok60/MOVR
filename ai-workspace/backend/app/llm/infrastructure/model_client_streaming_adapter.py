"""Streaming counterpart to DefaultLLMClientAdapter.

NOT confirmed to be backed by anything real — see
app/integrations/existing_model_client/README.md: nothing in the existing DefaultLLMClient
contract, as described, exposes a streaming method. This class exists as the seam
llm_stream_service.py calls through, so that IF/WHEN the existing client gains streaming
support, only this file changes. Until then, `stream_completion` raises rather than
silently falling back to non-streaming, so a caller can't mistake a fake stream for a real one.
"""

from collections.abc import Iterator

class ModelClientStreamingNotSupportedError(NotImplementedError):
    pass


class ModelClientStreamingAdapter:
    def __init__(self, db, tenant_id: str):
        from worktop.core_services.app.gen_ai_models.default_llm_client import DefaultLLMClient

        self._client = DefaultLLMClient(db=db, tenant_id=tenant_id)

    def stream_completion(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        if not hasattr(self._client, "stream_completion"):
            raise ModelClientStreamingNotSupportedError(
                "DefaultLLMClient does not expose a streaming method as currently understood — "
                "see app/integrations/existing_model_client/README.md"
            )
        input_data = self._client.prepare_input(system_prompt=system_prompt, user_prompt=user_prompt)
        yield from self._client.stream_completion(input_data)
