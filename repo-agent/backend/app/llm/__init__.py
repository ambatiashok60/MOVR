"""LLM abstraction: a deterministic FakeLLM (default) and a lazy Bedrock client."""

from app.llm.base import LLMClient
from app.llm.client_factory import build_llm_client

__all__ = ["LLMClient", "build_llm_client"]
