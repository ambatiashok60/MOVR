"""Credential-error classifier + Markdown code-fence integrity."""

from __future__ import annotations

from app.llm.exceptions import is_credential_error
from app.streaming.response_batcher import MarkdownStreamState


class _ClientError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class NoCredentialsError(Exception):
    pass


def test_credential_error_by_code():
    assert is_credential_error(_ClientError("ExpiredTokenException")) is True
    assert is_credential_error(_ClientError("UnrecognizedClientException")) is True
    assert is_credential_error(_ClientError("SomethingElse")) is False


def test_credential_error_by_type_name():
    assert is_credential_error(NoCredentialsError()) is True
    assert is_credential_error(ValueError("nope")) is False


def test_unclosed_fence_gets_closed():
    state = MarkdownStreamState()
    state.observe("Here is code:\n```python\nprint('x')\n")  # opened, never closed
    assert state.inside_code_fence is True
    assert state.closing_if_needed() == "\n```\n"


def test_balanced_fence_needs_no_close():
    state = MarkdownStreamState()
    state.observe("```python\nprint('x')\n```\n")
    assert state.inside_code_fence is False
    assert state.closing_if_needed() == ""
