# Existing model client — assumed contract

This package intentionally contains no model-calling code of its own. AI Workspace calls into
the existing `worktop.core_services.app.gen_ai_models` package (already in production, per this
session's screenshots) through `app/llm/infrastructure/model_client_factory_adapter.py`.

**This file documents what that adapter assumes exists.** It's reconstructed from screenshots
described in conversation, not from reading the real source — treat every signature below as
unconfirmed until checked against the actual module.

## Assumed import paths

```python
from worktop.core_services.app.gen_ai_models.model_client_factory import ModelClientFactory
from worktop.core_services.app.gen_ai_models.default_llm_client import DefaultLLMClient  # path guessed — only the class name was shown
```

## Assumed `DefaultLLMClient` contract

```python
class DefaultLLMClient:
    def __init__(self, db, tenant_id):
        # loads model_info, model_params, and model_config (via ModelsConfigurationDAO)
        # internally, then resolves self.provider = self.model_config.get("provider_name")
        # and does self.client = ModelClientFactory.get_client(self.provider, self.model_config,
        # self.model_params, db, tenant_id)
        ...

    def prepare_input(self, system_prompt: str, user_prompt: str):
        ...

    def generate_completion(self, input_data):
        ...
```

## What AI Workspace assumes it can rely on

- `DefaultLLMClient(db, tenant_id)` fully resolves provider + model config internally — the
  adapter never passes a provider name or model id into the constructor.
- `prepare_input()` and `generate_completion()` are synchronous and provider-agnostic — the same
  two calls work regardless of which provider `ModelsConfigurationDAO` resolves to.
- Per-tenant model selection already exists somewhere in `model_config` — `model_catalog_service.py`
  needs a read path into that (not yet identified) to power the "select which model to use" UI
  affordance, since nothing in the screenshots showed how a tenant's *available* models (as
  opposed to their *currently configured* one) are listed.

## What's explicitly NOT assumed

- **Streaming.** Nothing in the screenshots showed a streaming method on `DefaultLLMClient`.
  `llm_stream_service.py` and `model_client_streaming_adapter.py` exist as forward-looking seams
  but are not wired to a real streaming call — see the TODO in those files.
- **Async.** `prepare_input`/`generate_completion` are treated as synchronous. If the real client
  is async, the adapter needs `await` added and the calling services need to become async too.

## Before relying on this integration

Read the real `worktop/core_services/app/gen_ai_models/` source and correct every assumption
above. This README exists so that correction is a one-file diff, not an archaeology project
across every service that calls into the LLM layer.
