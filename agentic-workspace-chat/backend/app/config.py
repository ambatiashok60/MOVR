from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    aws_profile: str
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"
    bedrock_max_tokens: int = 4096
    workspace_allowed_roots: list[Path]
    workspace_max_files: int = 10_000
    workspace_max_file_bytes: int = 1_048_576
    agent_max_steps: int = 12
    agent_state_dir: Path = Path(".agent-state")
    custom_tool_timeout_seconds: int = 5
    frontend_origin: str = "http://localhost:4200"

    @field_validator("workspace_allowed_roots", mode="before")
    @classmethod
    def split_roots(cls, value: object) -> object:
        return value.split(",") if isinstance(value, str) else value


@lru_cache
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
