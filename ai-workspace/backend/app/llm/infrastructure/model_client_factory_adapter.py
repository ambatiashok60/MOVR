from app.llm.infrastructure.default_llm_client_adapter import DefaultLLMClientAdapter


class ModelClientFactoryAdapter(DefaultLLMClientAdapter):
    """Backward-compatible name for the older AI Workspace adapter.

    New code should use DefaultLLMClientAdapter through LLMClientFactory, matching
    test-agent's model wiring pattern.
    """
