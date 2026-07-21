"""Selects the LLM implementation from settings. All model creation routes
through here — agent logic never constructs a client directly.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from app.config import settings
from app.llm.base import LLMClient
from app.llm.fake_llm import FakeLLM

ReauthCallback = Callable[[str], Awaitable[None]]


def build_llm_client(
    *,
    provider: str | None = None,
    profile: str | None = None,
    region: str | None = None,
    model_id: str | None = None,
    on_reauth_required: ReauthCallback | None = None,
    on_reauthenticated: ReauthCallback | None = None,
) -> LLMClient:
    provider = (provider or settings.llm_provider).lower()

    if provider == "fake":
        return FakeLLM()

    if provider == "bedrock":
        # Imported here so the AWS stack is only touched when actually selected.
        from app.llm.aws_session_manager import AwsSessionManager
        from app.llm.bedrock_client import BedrockClient
        from app.llm.sso_login_service import SsoLoginService

        prof = profile if profile is not None else settings.aws_profile
        reg = region or settings.aws_region
        session_manager = AwsSessionManager(prof, reg)
        return BedrockClient(
            session_manager=session_manager,
            login_service=SsoLoginService(),
            profile_name=prof,
            model_id=model_id or settings.bedrock_model_id,
            on_reauth_required=on_reauth_required,
            on_reauthenticated=on_reauthenticated,
        )

    raise ValueError(f"Unknown LLM provider: {provider}")
