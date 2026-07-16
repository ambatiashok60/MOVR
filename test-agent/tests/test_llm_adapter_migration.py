"""Tests for the migrated DefaultLLMClientAdapter.

Covers the two things the migration is responsible for:

* Worktop client construction through the sole direct ``ModelClientFactory``
  path, with tenant normalization and provider resolution.
* The adapter's own contract — caller-supplied system prompts, response
  normalization across provider shapes, and schema-aware structured parsing
  with a single repair attempt.

The external ``worktop.core_services`` package is not installed in this
environment, so the wiring tests inject fake modules into ``sys.modules`` to
assert the adapter calls the real signatures with the right arguments.
"""

from __future__ import annotations

import sys
import types

import pytest
from pydantic import BaseModel

from worktop.test_agent.app.llm.default_llm_client import DefaultLLMClientAdapter


# --------------------------------------------------------------------------- #
# Fakes for the external worktop.core_services surface
# --------------------------------------------------------------------------- #
_CORE_MODULES = [
    "worktop.core_services",
    "worktop.core_services.app",
    "worktop.core_services.app.gen_ai_models",
    "worktop.core_services.app.gen_ai_models.model_client_factory",
    "worktop.core_services.app.dao",
    "worktop.core_services.app.dao.models_config_dao",
    "worktop.core_services.app.utility",
    "worktop.core_services.app.utility.common_utils",
]


def _install_core_services(monkeypatch, *, dao_cls, factory_cls, common_utils_cls):
    """Register fake core_services modules so lazy adapter imports resolve."""
    modules: dict[str, types.ModuleType] = {}
    for name in _CORE_MODULES:
        modules[name] = types.ModuleType(name)

    modules[
        "worktop.core_services.app.dao.models_config_dao"
    ].ModelsConfigurationDAO = dao_cls
    modules[
        "worktop.core_services.app.gen_ai_models.model_client_factory"
    ].ModelClientFactory = factory_cls
    modules[
        "worktop.core_services.app.utility.common_utils"
    ].CommonUtils = common_utils_cls

    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)


class _StubProviderClient:
    """Provider client returned by ModelClientFactory."""

    def __init__(self, provider="anthropic", response="generated text"):
        self.provider = provider
        self._response = response
        self.prepared_with = None
        self.completed_with = None

    def prepare_input(self, system_prompt, user_prompt):
        self.prepared_with = {"system": system_prompt, "user": user_prompt}
        return self.prepared_with

    def generate_completion(self, input_data):
        self.completed_with = input_data
        return self._response


# --------------------------------------------------------------------------- #
# Tenant-id normalization
# --------------------------------------------------------------------------- #
class TestNormalizeTenantId:
    def test_integer_passthrough(self):
        assert DefaultLLMClientAdapter._normalize_tenant_id(12) == 12

    def test_numeric_string(self):
        assert DefaultLLMClientAdapter._normalize_tenant_id("12") == 12

    def test_numeric_string_with_whitespace(self):
        assert DefaultLLMClientAdapter._normalize_tenant_id("  7 ") == 7

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError):
            DefaultLLMClientAdapter._normalize_tenant_id("   ")

    def test_non_numeric_string_rejected(self):
        with pytest.raises(ValueError):
            DefaultLLMClientAdapter._normalize_tenant_id("tenant-1")

    def test_boolean_rejected(self):
        with pytest.raises(ValueError):
            DefaultLLMClientAdapter._normalize_tenant_id(True)


# --------------------------------------------------------------------------- #
# Client construction wiring
# --------------------------------------------------------------------------- #
class TestClientConstruction:
    def test_constructs_provider_through_direct_factory(self, monkeypatch):
        calls = {}

        class FakeCommonUtils:
            @staticmethod
            def load_model_info(db, tenant_id):
                calls["load_model_info"] = (db, tenant_id)
                return {"model_params": {"temperature": 0.1}}

        class FakeDAO:
            def __init__(self, db):
                calls["dao_db"] = db

            def get_model_config_by_tenant_id(self, tenant_id):
                calls["dao_tenant"] = tenant_id
                return {"provider_name": "bedrock", "model_id": "claude"}

        class FakeFactory:
            @staticmethod
            def get_client(provider, model_config, model_params, db, tenant_id):
                calls["get_client"] = (provider, model_config, model_params, db, tenant_id)
                return _StubProviderClient(provider=provider)

        _install_core_services(
            monkeypatch,
            dao_cls=FakeDAO,
            factory_cls=FakeFactory,
            common_utils_cls=FakeCommonUtils,
        )

        adapter = DefaultLLMClientAdapter(db="DB", tenant_id=42)

        assert adapter.provider == "bedrock"
        assert calls["load_model_info"] == ("DB", 42)
        assert calls["dao_db"] == "DB"
        assert calls["dao_tenant"] == 42
        provider, model_config, model_params, db, tenant_id = calls["get_client"]
        assert provider == "bedrock"
        assert model_config == {"provider_name": "bedrock", "model_id": "claude"}
        assert model_params == {"temperature": 0.1}
        assert db == "DB"
        assert tenant_id == 42

    def test_missing_provider_raises(self, monkeypatch):
        class FakeCommonUtils:
            @staticmethod
            def load_model_info(db, tenant_id):
                return {"model_params": {}}

        class FakeDAO:
            def __init__(self, db):
                pass

            def get_model_config_by_tenant_id(self, tenant_id):
                return {}  # no provider_name

        class FakeFactory:
            @staticmethod
            def get_client(*args, **kwargs):
                raise AssertionError("factory must not be called without a provider")

        _install_core_services(
            monkeypatch,
            dao_cls=FakeDAO,
            factory_cls=FakeFactory,
            common_utils_cls=FakeCommonUtils,
        )

        with pytest.raises(RuntimeError, match="No provider_name configured"):
            DefaultLLMClientAdapter(db="DB", tenant_id=1)


# --------------------------------------------------------------------------- #
# complete()
# --------------------------------------------------------------------------- #
def _adapter_with_client(client, provider="anthropic"):
    adapter = object.__new__(DefaultLLMClientAdapter)
    adapter._db = "DB"
    adapter._tenant_id = 1
    adapter._provider = provider
    adapter._client = client
    return adapter


class TestComplete:
    def test_forwards_system_and_user_prompt(self):
        client = _StubProviderClient(response="the answer")
        adapter = _adapter_with_client(client)

        result = adapter.complete("do the thing", system_prompt="be terse")

        assert result == "the answer"
        assert client.prepared_with == {"system": "be terse", "user": "do the thing"}
        assert client.completed_with == client.prepared_with

    def test_default_system_prompt_is_empty_string(self):
        client = _StubProviderClient()
        adapter = _adapter_with_client(client)

        adapter.complete("do the thing")

        assert client.prepared_with["system"] == ""

    def test_empty_prompt_rejected(self):
        adapter = _adapter_with_client(_StubProviderClient())
        with pytest.raises(ValueError, match="prompt cannot be empty"):
            adapter.complete("   ")

    def test_empty_response_is_wrapped_error(self):
        adapter = _adapter_with_client(_StubProviderClient(response="   "))
        with pytest.raises(RuntimeError, match="LLM completion failed"):
            adapter.complete("prompt")

    def test_provider_must_implement_generate_completion(self):
        class ClientWithoutGenerate:
            def prepare_input(self, system_prompt, user_prompt):
                return user_prompt

        adapter = _adapter_with_client(ClientWithoutGenerate())
        with pytest.raises(RuntimeError, match="LLM completion failed"):
            adapter.complete("hi")


# --------------------------------------------------------------------------- #
# Response normalization
# --------------------------------------------------------------------------- #
class TestExtractText:
    def setup_method(self):
        self.adapter = object.__new__(DefaultLLMClientAdapter)

    def test_plain_string(self):
        assert self.adapter._extract_text("hello") == "hello"

    def test_dict_content(self):
        assert self.adapter._extract_text({"content": "hi"}) == "hi"

    def test_nested_message(self):
        assert self.adapter._extract_text({"message": {"content": "deep"}}) == "deep"

    def test_openai_choices(self):
        response = {"choices": [{"message": {"content": "picked"}}]}
        assert self.adapter._extract_text(response) == "picked"

    def test_list_content_blocks(self):
        response = {"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}
        assert self.adapter._extract_text(response) == "ab"

    def test_top_level_list_blocks(self):
        assert self.adapter._extract_text([{"type": "text", "text": "x"}]) == "x"

    def test_object_with_content_attr(self):
        obj = types.SimpleNamespace(content="from attr")
        assert self.adapter._extract_text(obj) == "from attr"

    def test_object_with_list_content_attr(self):
        obj = types.SimpleNamespace(content=[{"type": "text", "text": "attrlist"}])
        assert self.adapter._extract_text(obj) == "attrlist"

    def test_unknown_object_is_rejected(self):
        with pytest.raises(TypeError, match="supported text field"):
            self.adapter._extract_text(12345)


# --------------------------------------------------------------------------- #
# Structured completion
# --------------------------------------------------------------------------- #
class _Decision(BaseModel):
    verdict: str
    confidence: float


class _ScriptedAdapter(DefaultLLMClientAdapter):
    """Adapter whose complete() returns scripted responses in order."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.completed_prompts = []

    def complete(self, prompt, system_prompt=None):
        self.completed_prompts.append((prompt, system_prompt))
        return self._responses.pop(0)


class TestStructuredCompletion:
    def test_build_structured_prompt_includes_schema(self):
        adapter = object.__new__(DefaultLLMClientAdapter)
        prompt = adapter._build_structured_prompt("rank these", _Decision)
        assert "rank these" in prompt
        assert "JSON schema" in prompt
        assert '"verdict"' in prompt

    def test_clean_object(self):
        adapter = _ScriptedAdapter(['{"verdict": "yes", "confidence": 0.9}'])
        result = adapter.complete_structured("prompt", _Decision)
        assert result.verdict == "yes"
        assert len(adapter.completed_prompts) == 1

    def test_prose_wrapped_json(self):
        adapter = _ScriptedAdapter(
            ['Sure! Here it is:\n{"verdict": "no", "confidence": 0.2}\nHope that helps.']
        )
        result = adapter.complete_structured("prompt", _Decision)
        assert result.verdict == "no"

    def test_fenced_json(self):
        adapter = _ScriptedAdapter(
            ['```json\n{"verdict": "maybe", "confidence": 0.5}\n```']
        )
        result = adapter.complete_structured("prompt", _Decision)
        assert result.verdict == "maybe"

    def test_repairs_invalid_first_response(self):
        adapter = _ScriptedAdapter(
            [
                '{"verdict": {"nested": "bad"}, "confidence": 0.9}',
                '{"verdict": "recovered", "confidence": 0.7}',
            ]
        )
        result = adapter.complete_structured("prompt", _Decision)
        assert result.verdict == "recovered"
        # exactly two calls: initial + one repair
        assert len(adapter.completed_prompts) == 2
        # the repair call carries the repair system prompt
        assert adapter.completed_prompts[1][1] is not None

    def test_both_responses_invalid_raises(self):
        adapter = _ScriptedAdapter(
            [
                '{"verdict": {"x": 1}, "confidence": 0.9}',
                '{"still": "wrong"}',
            ]
        )
        with pytest.raises(Exception):
            adapter.complete_structured("prompt", _Decision)
        assert len(adapter.completed_prompts) == 2  # only one repair attempt
