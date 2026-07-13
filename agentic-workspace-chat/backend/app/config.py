from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def model_display_name(model_id: str) -> str:
    value = model_id.lower()
    if "sonnet-4-5" in value: return "Claude Sonnet 4.5"
    if "sonnet-4" in value: return "Claude Sonnet 4"
    if "haiku-4-5" in value: return "Claude Haiku 4.5"
    if "opus-4" in value: return "Claude Opus 4"
    if "claude" in value: return "Anthropic Claude"
    return model_id


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    aws_auth_mode: str = "sso"
    aws_profile: str = ""
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    bedrock_model_id: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"
    bedrock_max_tokens: int = 8192
    workspace_allowed_roots: Annotated[list[Path], NoDecode]
    workspace_max_files: int = 10_000
    workspace_max_file_bytes: int = 1_048_576
    agent_max_steps: int = 12
    agent_max_response_continuations: int = 3
    agent_state_dir: Path = Path(".agent-state")
    custom_tool_timeout_seconds: int = 5
    frontend_origin: str = "http://localhost:4200"

    @field_validator("workspace_allowed_roots", mode="before")
    @classmethod
    def split_roots(cls, value: object) -> object:
        return [part.strip() for part in value.split(",") if part.strip()] if isinstance(value, str) else value


@lru_cache
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
