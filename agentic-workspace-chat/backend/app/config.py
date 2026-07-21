import json
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
    bedrock_connect_timeout_seconds: int = 10
    bedrock_read_timeout_seconds: int = 120
    workspace_allowed_roots: Annotated[list[Path], NoDecode]
    workspace_max_files: int = 10_000
    workspace_max_file_bytes: int = 1_048_576
    agent_max_steps: int = 12
    # Extended budget that activates implicitly when the model publishes a plan
    # via update_plan — complex, multi-step work gets more room automatically.
    agent_max_steps_planned: int = 32
    agent_max_response_continuations: int = 3
    # Conversation memory sent to the model per turn (bounded).
    agent_history_messages: int = 12
    agent_history_max_chars: int = 24_000
    # Allowlisted validation commands the agent may execute per run.
    agent_max_command_runs: int = 5
    agent_state_dir: Path = Path(".agent-state")
    custom_tool_timeout_seconds: int = 5
    frontend_origin: str = "http://localhost:4200"
    # Optional bearer token for deployments where the local UI is not enough
    # isolation. Empty keeps localhost development backwards compatible.
    api_auth_token: str = ""
    max_request_bytes: int = 2_000_000
    request_timeout_seconds: int = 300

    @field_validator("workspace_allowed_roots", mode="before")
    @classmethod
    def split_roots(cls, value: object) -> object:
        """Accept both env formats: a JSON array or a comma-separated string.

        A JSON-style value fed through the comma splitter would keep the
        literal brackets/quotes inside the path and every workspace check
        would fail with 403, so JSON is parsed first. Individual entries are
        stripped of whitespace and surrounding quotes.
        """
        if not isinstance(value, str):
            return value
        text = value.strip()
        parts: list[str]
        if text.startswith("["):
            try:
                loaded = json.loads(text)
            except json.JSONDecodeError:
                loaded = None
            if isinstance(loaded, list):
                parts = [str(item) for item in loaded]
            else:
                parts = text.split(",")
        else:
            parts = text.split(",")
        cleaned = [part.strip().strip("\"'").strip() for part in parts]
        return [part for part in cleaned if part]


@lru_cache
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
