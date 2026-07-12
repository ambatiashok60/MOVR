from dataclasses import dataclass
from typing import Protocol

from worktop.ai_workspace.app.llm.application.llm_client import LLMClient


@dataclass
class LLMCompletion:
    text: str
    provider: str | None
    raw_response: object


class LLMGateway(Protocol):
    """The only interface ai_workspace/ code depends on for calling a model. Swapping the
    underlying adapter (e.g. if the existing client's contract changes) only ever means
    changing what implements this protocol, not every call site."""

    def complete(self, system_prompt: str, user_prompt: str) -> LLMCompletion: ...


class ModelClientFactoryGateway:
    """Default LLMGateway implementation for the LLMClient created by LLMClientFactory."""

    def __init__(self, client: LLMClient):
        self._client = client

    def complete(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        text = self._client.complete(system_prompt=system_prompt, user_prompt=user_prompt)
        return LLMCompletion(text=text, provider=getattr(self._client, "provider", None), raw_response=text)
