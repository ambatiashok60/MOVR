"""Owns the single boto3 Session + Bedrock client and can reset them.

boto3 is imported lazily inside methods so the module (and the whole app) loads
without the AWS SDK installed.
"""

from __future__ import annotations

from typing import Any

from app.llm.exceptions import LLMConfigurationError


class AwsSessionManager:
    def __init__(self, profile_name: str, region_name: str) -> None:
        self.profile_name = profile_name
        self.region_name = region_name
        self._session: Any | None = None
        self._bedrock_client: Any | None = None

    def _boto3(self):
        try:
            import boto3  # lazy: only needed for real AWS
        except ImportError as exc:  # pragma: no cover - depends on env
            raise LLMConfigurationError(
                "boto3 is not installed; install it or set REPO_AGENT_LLM_PROVIDER=fake"
            ) from exc
        return boto3

    def create_session(self):
        boto3 = self._boto3()
        kwargs: dict[str, Any] = {"region_name": self.region_name}
        if self.profile_name:
            kwargs["profile_name"] = self.profile_name
        self._session = boto3.Session(**kwargs)
        return self._session

    def get_bedrock_client(self):
        if self._session is None:
            self.create_session()
        if self._bedrock_client is None:
            self._bedrock_client = self._session.client("bedrock-runtime")
        return self._bedrock_client

    def reset(self) -> None:
        """Drop cached session/client so the next call rebuilds from the
        provider chain (picking up refreshed SSO credentials)."""
        self._session = None
        self._bedrock_client = None
